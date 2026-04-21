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
    batch = Option(require=False, default=True, validate=validators.Boolean())

    def get_credentials(self, service):
        # PERBAIKAN: Langsung membaca API Key dari gemini_settings.conf bawaan Deployer
        try:
            return service.confs['gemini_settings']['gemini_config']['api_key']
        except Exception:
            return None

    def get_default_model(self, service):
        try:
            return service.confs['gemini_settings']['gemini_config']['model_name']
        except:
            return "gemma-4-31b-it"

    def call_gemini_api(self, text_payload):
        safe_model = urllib.parse.quote(self.active_model, safe='')
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{safe_model}:generateContent?key={self.api_key}"
        
        payload = {
            "contents": [{"parts": [{"text": text_payload}]}]
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
        setup_model = self.get_default_model(service)
        self.active_model = self.model if self.model else (setup_model if setup_model else "gemma-4-31b-it")
        
        if not self.api_key:
            raise Exception("API Key belum dikonfigurasi. Silakan perbarui melalui UI Deployer.")

    def stream(self, records):
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

            combined_logs = "\n--- EVENT SEPARATOR ---\n".join(all_events)
            full_prompt = f"{self.prompt}\n\n[INFO: Menampilkan {len(all_events)} log]\nBerikut adalah gabungan seluruh log untuk dianalisis secara kolektif:\n\n{combined_logs}"
            
            analysis = self.call_gemini_api(full_prompt)
            yield {
                "total_events_analyzed": len(all_events),
                "gemini_analysis": analysis,
                "analysis_mode": "batch"
            }
        else:
            for record in records:
                log_content = record.get(self.field, "")
                if log_content:
                    full_prompt = f"{self.prompt}\n\nData Log:\n{log_content}"
                    record['gemini_analysis'] = self.call_gemini_api(full_prompt)
                    record['analysis_mode'] = "single"
                yield record

if __name__ == "__main__":
    dispatch(GeminiAnalyzeCommand, sys.argv, sys.stdin, sys.stdout, __name__)