#!/usr/bin/env python
import sys
import json
import urllib.request
import urllib.parse
from splunklib.searchcommands import dispatch, StreamingCommand, Configuration, Option, validators
import splunklib.client as client

@Configuration()
class GeminiAnalyzeCommand(StreamingCommand):
    prompt = Option(require=True)
    field = Option(require=False, default="_raw") 
    model = Option(require=False)
    batch = Option(require=False, default=False, validate=validators.Boolean())
    role = Option(require=False)

    def get_credentials(self, service):
        for pw in service.storage_passwords:
            if pw.realm == "gemini_soc_assistant_realm":
                return pw.clear_password
        return None

    def get_conf_value(self, service, stanza, key, default=None):
        try:
            return service.confs['gemini_settings'][stanza][key]
        except:
            return default

    def extract_log_data(self, record):
        """Mendeteksi data: Jika _raw tidak ada, ambil seluruh row sebagai JSON."""
        val = record.get(self.field)
        if val and str(val).strip() != "":
            return str(val)
        else:
            # Ambil semua field yang bukan internal Splunk (_)
            row_data = {k: v for k, v in record.items() if not k.startswith('_')}
            return json.dumps(row_data) if row_data else "No data found in row."

    def call_gemini_api(self, text_payload, system_instruction, role_name):
        safe_model = urllib.parse.quote(self.active_model, safe='')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{safe_model}:generateContent?key={self.api_key}"
        
        # PROMPT SHIELD: Memaksa AI untuk berhenti menjabarkan role dan langsung menganalisa.
        instruction_block = system_instruction if system_instruction else "Anda adalah Analis SOC Senior."
        
        final_text = (
            f"COMMAND: Analisis data berikut menggunakan persona: {instruction_block}\n\n"
            f"DATA UNTUK DIANALISIS:\n{text_payload}\n\n"
            f"INSTRUKSI KHUSUS: {self.prompt}\n\n"
            f"ATURAN OUTPUT:\n"
            f"- JANGAN perkenalkan diri atau mengulang instruksi ini.\n"
            f"- JANGAN tampilkan proses berpikir atau draf.\n"
            f"- LANGSUNG berikan hasil akhir analisa yang detail, teknis, dan komprehensif.\n"
            f"- Gunakan format Markdown (Tabel, Heading, Bullet points).\n"
            f"HASIL ANALISA:"
        )

        payload = {"contents": [{"parts": [{"text": final_text}]}]}
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                return res_data['candidates'][0]['content']['parts'][0]['text'], final_text
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode('utf-8')
            return f"API Error: {err_msg}", final_text
        except Exception as e:
            return f"System Error: {str(e)}", final_text

    def prepare(self):
        service = client.connect(token=self._metadata.searchinfo.session_key)
        self.api_key = self.get_credentials(service)
        
        # Fallback Default: gemma-4-31b-it
        self.active_model = self.model if self.model else self.get_conf_value(service, 'gemini_config', 'model_name', 'gemma-4-31b-it')
        
        active_role = self.role if self.role else self.get_conf_value(service, 'gemini_config', 'default_role', 'soc_analyst_id')
        self.system_prompt = self.get_conf_value(service, f"role:{active_role}", "instructions")
        self.role_name = active_role

        if not self.api_key:
            raise Exception("API Key belum dikonfigurasi. Silakan masuk ke menu Setup.")

    def stream(self, records):
        if self.batch:
            # MODE BATCH: Menggabungkan semua log menjadi satu prompt besar
            all_logs = []
            for record in records:
                content = self.extract_log_data(record)
                all_logs.append(content)
            
            if not all_logs: return

            combined_payload = "\n--- LOG SEPARATOR ---\n".join(all_logs)
            analysis, sent_prompt = self.call_gemini_api(combined_payload, self.system_prompt, self.role_name)
            
            yield {
                "gemini_analysis": analysis,
                "gemini_prompt": sent_prompt, # Field audit untuk melihat apa yang dikirim
                "analysis_mode": "batch",
                "ai_model": self.active_model,
                "ai_role": self.role_name,
                "event_count": len(all_logs)
            }
        else:
            # MODE SINGLE: Analisa satu per satu row
            for record in records:
                log_content = self.extract_log_data(record)
                analysis, sent_prompt = self.call_gemini_api(log_content, self.system_prompt, self.role_name)
                
                record['gemini_analysis'] = analysis
                record['gemini_prompt'] = sent_prompt
                record['analysis_mode'] = "single"
                record['ai_model'] = self.active_model
                record['ai_role'] = self.role_name
                yield record

if __name__ == "__main__":
    dispatch(GeminiAnalyzeCommand, sys.argv, sys.stdin, sys.stdout, __name__)