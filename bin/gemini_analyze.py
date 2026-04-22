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
    # Default tetap _raw, tapi kita akan buat logika cerdas jika _raw tidak ada
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
        """
        Fungsi cerdas untuk mengambil data log.
        Jika field spesifik (misal _raw) tidak ada, otomatis ubah seluruh baris menjadi JSON.
        """
        val = record.get(self.field)
        if val:
            return str(val)
        else:
            # Mengabaikan field internal Splunk yang diawali dengan '_' (kecuali _time jika diperlukan)
            clean_rec = {k: v for k, v in record.items() if not k.startswith('_')}
            if not clean_rec:
                return ""
            return json.dumps(clean_rec)

    def call_gemini_api(self, text_payload, system_instruction=None):
        safe_model = urllib.parse.quote(self.active_model, safe='')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{safe_model}:generateContent?key={self.api_key}"
        
        # PERBAIKAN PROMPT ENGINEERING: Mencegah AI mencetak "proses berpikirnya" (CoT)
        if system_instruction:
            final_text = (
                f"Terapkan instruksi role ini secara ketat:\n"
                f"\"{system_instruction}\"\n\n"
                f"ATURAN MUTLAK:\n"
                f"1. OUTPUT HANYA HASIL AKHIR. Dilarang keras menampilkan proses berpikir (chain of thought), draf, outline, atau rencana jawaban.\n"
                f"2. Jangan gunakan kalimat basa-basi seperti 'Baik, ini analisanya'. Langsung berikan hasil.\n\n"
                f"=== TUGAS DAN DATA ===\n"
                f"{text_payload}"
            )
        else:
            final_text = text_payload

        payload = {
            "contents": [{"parts": [{"text": final_text}]}]
        }

        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                return res_data['candidates'][0]['content']['parts'][0]['text'], final_text
                
        except urllib.error.HTTPError as e:
            error_response = e.read().decode('utf-8')
            try:
                error_json = json.loads(error_response)
                return f"API Error ({e.code}): {error_json['error']['message']}", final_text
            except:
                return f"HTTP Error ({e.code}): {error_response}", final_text
                
        except Exception as e:
            return f"System Error: {str(e)}", final_text

    def prepare(self):
        service = client.connect(token=self._metadata.searchinfo.session_key)
        self.api_key = self.get_credentials(service)
        
        setup_model = self.get_conf_value(service, 'gemini_config', 'model_name', 'gemma-4-31b-it')
        self.active_model = self.model if self.model else setup_model
        
        setup_role = self.get_conf_value(service, 'gemini_config', 'default_role', 'soc_analyst_id')
        self.active_role_name = self.role if self.role else setup_role
        self.system_prompt = self.get_conf_value(service, f"role:{self.active_role_name}", "instructions")

        if not self.api_key:
            raise Exception("API Key belum terkonfigurasi di Credential Store.")

    def stream(self, records):
        if self.batch:
            all_events = []
            for record in records:
                content = self.extract_log_data(record)
                if content: all_events.append(content)
            
            if not all_events: return

            combined_logs = "\n--- EVENT DATA ---\n".join(all_events)
            full_prompt = f"{self.prompt}\n\n[Menganalisis {len(all_events)} Data Secara Kolektif]:\n{combined_logs}"
            
            # API sekarang mengembalikan 2 nilai: hasil AI dan prompt asli yang dikirim
            analysis, sent_prompt = self.call_gemini_api(full_prompt, self.system_prompt)
            
            yield {
                "gemini_analysis": analysis,
                "gemini_prompt": sent_prompt,  # FITUR BARU: Output prompt untuk debugging
                "analysis_mode": "batch",
                "ai_model": self.active_model,
                "ai_role": self.active_role_name
            }
        else:
            for record in records:
                log_content = self.extract_log_data(record)
                if log_content:
                    full_prompt = f"{self.prompt}\n\nData:\n{log_content}"
                    
                    analysis, sent_prompt = self.call_gemini_api(full_prompt, self.system_prompt)
                    
                    record['gemini_analysis'] = analysis
                    record['gemini_prompt'] = sent_prompt  # FITUR BARU: Output prompt
                    record['analysis_mode'] = "single"
                    record['ai_model'] = self.active_model
                    record['ai_role'] = self.active_role_name
                yield record

if __name__ == "__main__":
    dispatch(GeminiAnalyzeCommand, sys.argv, sys.stdin, sys.stdout, __name__)