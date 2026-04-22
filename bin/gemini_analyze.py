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
    # V2: Default sekarang adalah False (Single Mode)
    batch = Option(require=False, default=False, validate=validators.Boolean())
    role = Option(require=False)

    def get_credentials(self, service):
        """Membaca API Key dari Credential Store Search Head"""
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
        
        payload = {
            "contents": [{"parts": [{"text": text_payload}]}]
        }
        
        if system_instruction:
            payload["system_instruction"] = {
                "role": "system",
                "parts": [{"text": system_instruction}]
            }

        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                return res_data['candidates'][0]['content']['parts'][0]['text']
        except Exception as e:
            return f"Error: {str(e)}"

    def prepare(self):
        service = client.connect(token=self._metadata.searchinfo.session_key)
        self.api_key = self.get_credentials(service)
        
        # Penentuan Model: SPL > UI/Conf > Default
        setup_model = self.get_conf_value(service, 'gemini_config', 'model_name', 'gemini-3-flash')
        self.active_model = self.model if self.model else setup_model
        
        # Penentuan Role: SPL > UI/Conf > Default
        setup_role = self.get_conf_value(service, 'gemini_config', 'default_role', 'soc_analyst')
        self.active_role_name = self.role if self.role else setup_role
        self.system_prompt = self.get_conf_value(service, f"role:{self.active_role_name}", "instructions")

        if not self.api_key:
            raise Exception("API Key belum terkonfigurasi. Harap selesaikan setup di UI aplikasi.")

    def stream(self, records):
        if self.batch:
            all_events = []
            for record in records:
                content = record.get(self.field, "")
                if content: all_events.append(content)
            
            if not all_events: return

            combined_logs = "\n--- EVENT ---\n".join(all_events)
            full_prompt = f"{self.prompt}\n\n[Analisis Kolektif {len(all_events)} Log]:\n{combined_logs}"
            
            analysis = self.call_gemini_api(full_prompt, self.system_prompt)
            yield {
                "gemini_analysis": analysis,
                "analysis_mode": "batch",
                "ai_model": self.active_model,
                "ai_role": self.active_role_name
            }
        else:
            for record in records:
                log_content = record.get(self.field, "")
                if log_content:
                    full_prompt = f"{self.prompt}\n\nData:\n{log_content}"
                    record['gemini_analysis'] = self.call_gemini_api(full_prompt, self.system_prompt)
                    record['analysis_mode'] = "single"
                    record['ai_model'] = self.active_model
                    record['ai_role'] = self.active_role_name
                yield record

if __name__ == "__main__":
    dispatch(GeminiAnalyzeCommand, sys.argv, sys.stdin, sys.stdout, __name__)