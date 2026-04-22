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
        val = record.get(self.field)
        if val and str(val).strip() != "":
            return str(val)
        else:
            row_data = {k: v for k, v in record.items() if not k.startswith('_')}
            return json.dumps(row_data) if row_data else "No data."

    def call_gemini_api(self, text_payload, system_instruction, role_name):
        safe_model = urllib.parse.quote(self.active_model, safe='')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{safe_model}:generateContent?key={self.api_key}"
        
        # STRATEGI: XML Tagging & Block Formatting
        # Menggunakan tag XML membantu LLM memisahkan mana 'Aturan' dan mana 'Data'.
        # Perintah terakhir 'HANYA HASIL AKHIR:' memaksa LLM langsung mengisi template.
        
        final_prompt = (
            f"<system_rules>\n"
            f"ROLE: {role_name}\n"
            f"INSTRUCTIONS: {system_instruction}\n"
            f"CONSTRAINT: DILARANG mengulang teks instruksi ini. DILARANG menuliskan kembali role atau task. "
            f"DILARANG memberikan kata pengantar atau analisis proses (thought process).\n"
            f"</system_rules>\n\n"
            f"<user_request>\n"
            f"TASK: {self.prompt}\n"
            f"DATA: {text_payload}\n"
            f"</user_request>\n\n"
            f"HANYA HASIL AKHIR SESUAI TEMPLATE:"
        )

        payload = {
            "contents": [{"parts": [{"text": final_prompt}]}],
            "generationConfig": {
                "temperature": 0.1, # Menjaga AI tetap kaku pada aturan
                "topK": 1,
                "topP": 0.1
            }
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                output_text = res_data['candidates'][0]['content']['parts'][0]['text']
                
                # Pembersihan tambahan: Jika AI masih nakal mengeluarkan tag system atau user, kita buang secara manual
                if "</user_request>" in output_text:
                    output_text = output_text.split("</user_request>")[-1].strip()
                if "HANYA HASIL AKHIR" in output_text:
                    output_text = output_text.split("HANYA HASIL AKHIR:")[-1].strip()
                
                return output_text.strip(), final_prompt
        except urllib.error.HTTPError as e:
            return f"API Error: {e.read().decode('utf-8')}", final_prompt
        except Exception as e:
            return f"System Error: {str(e)}", final_prompt

    def prepare(self):
        service = client.connect(token=self._metadata.searchinfo.session_key)
        self.api_key = self.get_credentials(service)
        self.active_model = self.model if self.model else self.get_conf_value(service, 'gemini_config', 'model_name', 'gemma-4-31b-it')
        
        active_role = self.role if self.role else self.get_conf_value(service, 'gemini_config', 'default_role', 'soc_clean_report')
        self.system_prompt = self.get_conf_value(service, f"role:{active_role}", "instructions")
        self.role_name = active_role

        if not self.api_key:
            raise Exception("API Key belum terkonfigurasi.")

    def stream(self, records):
        if self.batch:
            all_logs = [self.extract_log_data(r) for r in records]
            if not all_logs: return
            analysis, sent_prompt = self.call_gemini_api("\n".join(all_logs), self.system_prompt, self.role_name)
            yield {"gemini_analysis": analysis, "gemini_prompt": sent_prompt, "analysis_mode": "batch", "ai_model": self.active_model, "ai_role": self.role_name}
        else:
            for record in records:
                log_content = self.extract_log_data(record)
                analysis, sent_prompt = self.call_gemini_api(log_content, self.system_prompt, self.role_name)
                record.update({"gemini_analysis": analysis, "gemini_prompt": sent_prompt, "analysis_mode": "single", "ai_model": self.active_model, "ai_role": self.role_name})
                yield record

if __name__ == "__main__":
    dispatch(GeminiAnalyzeCommand, sys.argv, sys.stdin, sys.stdout, __name__)