#!/usr/bin/env python
# =============================================================================
# Gemini SOC Assistant - gemini_analyze.py
# Version: 2.0
# Changelog:
#   - V2: Menggunakan Gemini API 'system_instruction' field secara native
#         agar sistem instruksi dan data pengguna benar-benar terpisah.
#   - V2: Temperature dinaikkan ke 0.4 agar output lebih ekspansif & detail.
#   - V2: maxOutputTokens ditambahkan agar analisis tidak terpotong.
#   - V2: Cleaning pipeline diperkuat: buang echo prompt, buang tag bocor.
#   - V2: Field 'gemini_analysis_length' ditambahkan untuk monitoring kualitas.
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

    # -----------------------------------------------------------------------
    # Helpers: credentials & config
    # -----------------------------------------------------------------------
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

    # -----------------------------------------------------------------------
    # Helpers: data extraction
    # -----------------------------------------------------------------------
    def extract_log_data(self, record):
        val = record.get(self.field)
        if val and str(val).strip():
            return str(val)
        row_data = {k: v for k, v in record.items() if not k.startswith('_')}
        return json.dumps(row_data, ensure_ascii=False) if row_data else "No data."

    # -----------------------------------------------------------------------
    # Output cleaning: hapus echo, tag bocor, dan noise
    # -----------------------------------------------------------------------
    def clean_output(self, text, user_prompt):
        # 1. Buang jika AI membocorkan tag XML sistem
        for tag in ["</user_request>", "</system_rules>", "<system_rules>", "<user_request>"]:
            if tag in text:
                text = text.split(tag)[-1]

        # 2. Buang jika AI mengulang marker header kita
        for marker in [
            "HASIL ANALISIS:",
            "ANALISIS KOMPREHENSIF:",
            "HASIL ANALISIS KOMPREHENSIF:",
        ]:
            if text.startswith(marker):
                text = text[len(marker):]

        # 3. Buang jika AI membeo (echo) prompt pengguna di awal output
        #    Hapus hingga 3 baris pertama yang mengandung kata dari prompt
        prompt_keywords = set(w.lower() for w in user_prompt.split() if len(w) > 4)
        lines = text.strip().splitlines()
        cleaned_lines = []
        skip_count = 0
        for line in lines:
            if skip_count < 3 and any(kw in line.lower() for kw in prompt_keywords):
                # Heuristik: baris pendek di awal yang hanya mengulang prompt -> skip
                if len(line.strip()) < 120:
                    skip_count += 1
                    continue
            cleaned_lines.append(line)

        return "\n".join(cleaned_lines).strip()

    # -----------------------------------------------------------------------
    # Gemini API call — V2: pakai 'system_instruction' native field
    # -----------------------------------------------------------------------
    def call_gemini_api(self, text_payload, system_instruction, role_name):
        safe_model = urllib.parse.quote(self.active_model, safe='')
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{safe_model}:generateContent?key={self.api_key}"
        )

        # --- System Instruction (dikirim via field terpisah, bukan di prompt) ---
        # Ini adalah cara NATIVE Gemini untuk memisahkan 'aturan sistem' dari 'data user'.
        # Hasilnya jauh lebih bersih — AI tidak perlu "melihat" instruksi sebagai bagian data.
        system_block = (
            f"{system_instruction}\n\n"
            f"ATURAN WAJIB OUTPUT:\n"
            f"1. Berikan analisis yang DETAIL, KOMPREHENSIF, dan MENDALAM.\n"
            f"2. DILARANG KERAS mengulang atau membeo (echo) teks dari task/prompt pengguna.\n"
            f"3. DILARANG memberi kata pengantar, basa-basi, salam, atau kalimat pembuka.\n"
            f"4. DILARANG menulis ulang data mentah apa adanya tanpa analisis.\n"
            f"5. Langsung mulai dengan TEMUAN, bukan dengan 'Berikut adalah analisis...'.\n"
            f"6. Gunakan format Markdown yang rapi (heading, bullet, bold) agar mudah dibaca.\n"
            f"7. Akhiri dengan bagian 'Rekomendasi Tindakan' yang actionable dan spesifik."
        )

        # --- User Turn (hanya berisi task + data mentah) ---
        user_turn = (
            f"TASK: {self.prompt}\n\n"
            f"DATA LOG:\n{text_payload}"
        )

        payload = {
            "system_instruction": {
                "parts": [{"text": system_block}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": user_turn}]
                }
            ],
            "generationConfig": {
                "temperature":    0.4,    # Cukup kreatif untuk analisis ekspansif, cukup deterministik untuk konsistensi
                "topK":           40,
                "topP":           0.95,
                "maxOutputTokens": 4096,  # Cegah analisis terpotong
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )

        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                res_data    = json.loads(response.read().decode('utf-8'))
                raw_text    = res_data['candidates'][0]['content']['parts'][0]['text']
                clean_text  = self.clean_output(raw_text, self.prompt)
                return clean_text, user_turn

        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8')
            return f"[API Error {e.code}]: {error_body}", user_turn
        except Exception as e:
            return f"[System Error]: {str(e)}", user_turn

    # -----------------------------------------------------------------------
    # prepare: ambil kredensial & konfigurasi sebelum stream dimulai
    # -----------------------------------------------------------------------
    def prepare(self):
        service          = client.connect(token=self._metadata.searchinfo.session_key)
        self.api_key     = self.get_credentials(service)
        self.active_model = (
            self.model if self.model
            else self.get_conf_value(service, 'gemini_config', 'model_name', 'gemma-4-31b-it')
        )
        active_role        = (
            self.role if self.role
            else self.get_conf_value(service, 'gemini_config', 'default_role', 'soc_clean_report')
        )
        self.system_prompt = self.get_conf_value(service, f"role:{active_role}", "instructions", "")
        self.role_name     = active_role

        if not self.api_key:
            raise Exception("[Gemini SOC v2] API Key belum terkonfigurasi. Buka menu Setup.")

    # -----------------------------------------------------------------------
    # stream: proses rekaman satu per satu atau batch
    # -----------------------------------------------------------------------
    def stream(self, records):
        if self.batch:
            all_logs = [self.extract_log_data(r) for r in records]
            if not all_logs:
                return
            combined   = "\n---\n".join(all_logs)
            analysis, sent_prompt = self.call_gemini_api(combined, self.system_prompt, self.role_name)
            yield {
                "gemini_analysis":        analysis,
                "gemini_analysis_length": str(len(analysis)),
                "gemini_task_sent":       sent_prompt,
                "analysis_mode":          "batch",
                "ai_model":               self.active_model,
                "ai_role":                self.role_name,
                "record_count":           str(len(all_logs)),
            }
        else:
            for record in records:
                log_content           = self.extract_log_data(record)
                analysis, sent_prompt = self.call_gemini_api(log_content, self.system_prompt, self.role_name)
                record.update({
                    "gemini_analysis":        analysis,
                    "gemini_analysis_length": str(len(analysis)),
                    "gemini_task_sent":       sent_prompt,
                    "analysis_mode":          "single",
                    "ai_model":               self.active_model,
                    "ai_role":                self.role_name,
                })
                yield record

if __name__ == "__main__":
    dispatch(GeminiAnalyzeCommand, sys.argv, sys.stdin, sys.stdout, __name__)