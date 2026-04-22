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
    # PERUBAHAN: Default batch sekarang False (Single Mode)
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

    def call_gemini_api(self, text_payload, system_instruction=None):
        safe_model = urllib.parse.quote(self.active_model, safe='')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{safe_model}:generateContent?key={self.api_key}"
        
        payload = {"contents": [{"parts": [{"text": text_payload}]}]}
        if system_instruction:
            payload["system_instruction"] = {"parts": {"text": system_instruction}}

        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                return res_data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            return f"Error API Gemini: {str(e)}"

    def prepare(self):
        service = client.connect(token=self._metadata.searchinfo.session_key)
        self.api_key = self.get_credentials(service)
        
        # Logika Model: Parameter SPL > UI Search Head > Default
        ui_model = self.get_conf_value(service, 'gemini_config', 'model_name', 'gemini-1.5-flash')
        self.active_model = self.model if self.model else ui_model
        
        # Logika Role: Parameter SPL > UI Search Head > Default
        ui_default_role = self.get_conf_value(service, 'gemini_config', 'default_role', 'default')
        self.active_role = self.role if self.role else ui_default_role
        
        # Ambil instruksi sistem berdasarkan Role yang terpilih
        self.system_instruction = self.get_conf_value(service, f"role:{self.active_role}", "instructions", None)

        if not self.api_key:
            raise Exception("API Key belum dikonfigurasi. Silakan simpan API Key di halaman Setup.")

    def stream(self, records):
        # --- MODE BATCH (Jika user mengetik batch=true) ---
        if self.batch:
            MAX_BATCH_SIZE = 1000
            all_events = []
            
            for i, record in enumerate(records):
                if i >= MAX_BATCH_SIZE:
                    break
                content = record.get(self.field, "")
                if content:
                    all_events.append(content)
            
            if not all_events:
                return

            combined_logs = "\n--- BATAS LOG ---\n".join(all_events)
            full_prompt = f"{self.prompt}\n\n[INFO BATCH: Menganalisis {len(all_events)} log sekaligus]\n\n{combined_logs}"
            
            analysis = self.call_gemini_api(full_prompt, self.system_instruction)
            yield {
                "total_events_analyzed": len(all_events),
                "gemini_analysis": analysis,
                "analysis_mode": "batch",
                "ai_model": self.active_model,
                "ai_role": self.active_role
            }
            
        # --- MODE SINGLE (Default, analisis baris per baris) ---
        else:
            for record in records:
                log_content = record.get(self.field, "")
                if log_content:
                    full_prompt = f"{self.prompt}\n\nData:\n{log_content}"
                    record['gemini_analysis'] = self.call_gemini_api(full_prompt, self.system_instruction)
                    record['analysis_mode'] = "single"
                    record['ai_model'] = self.active_model
                    record['ai_role'] = self.active_role
                yield record

if __name__ == "__main__":
    dispatch(GeminiAnalyzeCommand, sys.argv, sys.stdin, sys.stdout, __name__)