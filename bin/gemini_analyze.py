#!/usr/bin/env python
# =============================================================================
# Gemini SOC Assistant - gemini_analyze.py  |  Version: 2.1
# Changelog:
#   V2.1: Strict output cleaning pipeline + few-shot negative examples
#         dikirim ke AI agar AI TIDAK PERNAH mengulang prompt.
#         Temperature diturunkan ke 0.2 untuk konsistensi lebih tinggi.
#         maxOutputTokens naik ke 8192 untuk analisis yang lebih panjang.
# =============================================================================
import sys
import json
import re
import urllib.request
import urllib.parse
from splunklib.searchcommands import dispatch, StreamingCommand, Configuration, Option, validators
import splunklib.client as client

@Configuration()
class GeminiAnalyzeCommand(StreamingCommand):
    prompt = Option(require=True)
    field  = Option(require=False, default="_raw")
    model  = Option(require=False)
    batch  = Option(require=False, default=False, validate=validators.Boolean())
    role   = Option(require=False)

    def get_credentials(self, service):
        for pw in service.storage_passwords:
            if pw.realm == "gemini_soc_assistant_realm":
                return pw.clear_password
        return None

    def get_conf_value(self, service, stanza, key, default=None):
        try:
            return service.confs['gemini_settings'][stanza][key]
        except Exception:
            return default

    def extract_log_data(self, record):
        val = record.get(self.field)
        if val and str(val).strip():
            return str(val)
        row_data = {k: v for k, v in record.items() if not k.startswith('_')}
        return json.dumps(row_data, ensure_ascii=False) if row_data else "No data."

    def clean_output(self, text, user_prompt):
        """Multi-layer cleaning to eliminate echo and noise."""
        # Layer 1: Strip leaked XML tags
        for tag in ["</user_request>", "</system_rules>", "<system_rules>",
                    "<user_request>", "<data>", "</data>"]:
            if tag in text:
                text = text.split(tag)[-1]

        # Layer 2: Strip marker headers the AI echoes back
        markers = [
            "HASIL ANALISIS:", "ANALISIS KOMPREHENSIF:",
            "HASIL ANALISIS KOMPREHENSIF:", "ANALYSIS OUTPUT:",
        ]
        for m in markers:
            if text.upper().startswith(m.upper()):
                text = text[len(m):]

        # Layer 3: Strip lines that echo the user prompt verbatim
        prompt_lower = user_prompt.lower()
        lines = text.strip().splitlines()
        cleaned = []
        for line in lines:
            # If the line is short and is a near-verbatim repeat of the prompt, drop it
            if len(line.strip()) < 200 and line.strip().lower() in prompt_lower:
                continue
            cleaned.append(line)
        text = "\n".join(cleaned)

        # Layer 4: Strip common AI filler openers
        fillers = [
            "berikut adalah analisis", "berikut analisis", "berikut hasil analisis",
            "here is the analysis", "here is my analysis", "based on the provided",
            "berdasarkan data yang diberikan", "berdasarkan log yang diberikan",
            "saya akan menganalisis", "i will analyze",
        ]
        text_lower = text.lower().lstrip()
        for filler in fillers:
            if text_lower.startswith(filler):
                # Remove that opening sentence (up to first newline or period)
                idx = text.lower().find(filler)
                rest = text[idx + len(filler):]
                end = min(
                    (rest.find("\n") if rest.find("\n") != -1 else len(rest)),
                    (rest.find(".") + 1 if rest.find(".") != -1 else len(rest)),
                )
                text = rest[end:].strip()
                break

        return text.strip()

    def call_gemini_api(self, text_payload, system_instruction, role_name):
        safe_model = urllib.parse.quote(self.active_model, safe='')
        url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
               f"{safe_model}:generateContent?key={self.api_key}")

        # ── System Block ────────────────────────────────────────────────────
        # Dikirim via field 'system_instruction' native Gemini API.
        # Berisi: instruksi role + larangan eksplisit + few-shot negatif.
        system_block = (
            f"{system_instruction}\n\n"
            "═══ MANDATORY OUTPUT RULES ═══\n"
            "RULE 1: Start your response IMMEDIATELY. Do NOT write any intro sentence or greeting.\n"
            "RULE 2: NEVER repeat, paraphrase, or echo the user's TASK or question.\n"
            "RULE 3: NEVER write sentences like 'Based on the log...', 'Here is the analysis...', "
            "'Berikut analisis...', 'Berdasarkan data...', or similar filler openers.\n"
            "RULE 4: NEVER include the raw data back in your output verbatim.\n"
            "RULE 5: Format your output strictly according to the instructions (Markdown, JSON, or XML). "
            "Do not add conversational text outside of the requested format.\n\n"
            "── FEW-SHOT ANTI-PATTERN EXAMPLES (DO NOT DO THESE) ──\n"
            "❌ BAD: 'Berikut adalah analisis log EventID=4625 yang Anda kirimkan:'\n"
            "❌ BAD: 'Anda meminta saya untuk mengidentifikasi brute force...'\n"
            "❌ BAD: 'Based on the provided data, here is my analysis:'\n"
            "✅ GOOD: Start directly with the actual formatted response (e.g., Markdown headers, JSON brackets, or XML tags)."
        )

        # ── User Turn ───────────────────────────────────────────────────────
        user_turn = f"TASK: {self.prompt}\n\nDATA:\n{text_payload}"

        payload = {
            "system_instruction": {"parts": [{"text": system_block}]},
            "contents": [{"role": "user", "parts": [{"text": user_turn}]}],
            "generationConfig": {
                "temperature":     0.2,   # Low for strict rule-following
                "topK":            40,
                "topP":            0.90,
                "maxOutputTokens": 8192,
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )

        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                res_data   = json.loads(resp.read().decode('utf-8'))
                raw_text   = res_data['candidates'][0]['content']['parts'][0]['text']
                clean_text = self.clean_output(raw_text, self.prompt)
                return clean_text, user_turn
        except urllib.error.HTTPError as e:
            return f"[API Error {e.code}]: {e.read().decode('utf-8')}", user_turn
        except Exception as e:
            return f"[System Error]: {str(e)}", user_turn

    def prepare(self):
        service           = client.connect(token=self._metadata.searchinfo.session_key)
        self.api_key      = self.get_credentials(service)
        self.active_model = (self.model or
                             self.get_conf_value(service, 'gemini_config', 'model_name', 'gemma-4-31b-it'))
        active_role        = (self.role or
                              self.get_conf_value(service, 'gemini_config', 'default_role', 'soc_clean_report'))
        self.system_prompt = self.get_conf_value(service, f"role:{active_role}", "instructions", "")
        self.role_name     = active_role
        if not self.api_key:
            raise Exception("[Gemini SOC v2.1] API Key belum terkonfigurasi. Buka menu Setup.")

    def stream(self, records):
        if self.batch:
            all_logs = [self.extract_log_data(r) for r in records]
            if not all_logs:
                return
            combined          = "\n---\n".join(all_logs)
            analysis, sent    = self.call_gemini_api(combined, self.system_prompt, self.role_name)
            yield {
                "gemini_analysis":        analysis,
                "gemini_analysis_length": str(len(analysis)),
                "gemini_task_sent":       sent,
                "analysis_mode":          "batch",
                "ai_model":               self.active_model,
                "ai_role":                self.role_name,
                "record_count":           str(len(all_logs)),
            }
        else:
            for record in records:
                log_content        = self.extract_log_data(record)
                analysis, sent     = self.call_gemini_api(log_content, self.system_prompt, self.role_name)
                record.update({
                    "gemini_analysis":        analysis,
                    "gemini_analysis_length": str(len(analysis)),
                    "gemini_task_sent":       sent,
                    "analysis_mode":          "single",
                    "ai_model":               self.active_model,
                    "ai_role":                self.role_name,
                })
                yield record

if __name__ == "__main__":
    dispatch(GeminiAnalyzeCommand, sys.argv, sys.stdin, sys.stdout, __name__)