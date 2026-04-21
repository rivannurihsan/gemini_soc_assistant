#!/usr/bin/env python
import sys
import json
import urllib.request
from splunklib.searchcommands import dispatch, StreamingCommand, Configuration, Option, validators
import splunklib.client as client

@Configuration()
class GeminiAnalyzeCommand(StreamingCommand):
    prompt = Option(require=True)
    field = Option(require=False, default="_raw")
    # Opsi model agar user bisa override lewat query: | geminianalyze model="gemini-1.5-pro"
    model = Option(require=False)

    def get_credentials(self, service):
        for pw in service.storage_passwords:
            if pw.realm == "gemini_soc_assistant_realm":
                return pw.clear_password
        return None

    def get_default_model(self, service):
        try:
            return service.confs['gemini_settings']['gemini_config']['model_name']
        except:
            return "gemini-1.5-flash"

    def prepare(self):
        # Koneksi ke Splunk service
        service = client.connect(token=self._metadata.searchinfo.session_key)
        self.api_key = self.get_credentials(service)
        
        # Logika hirarki model:
        # 1. Parameter di SPL command (| geminianalyze model="xxx")
        # 2. Pengaturan di UI Setup
        # 3. Fallback ke gemma-2-27b-it
        setup_model = self.get_default_model(service)
        self.active_model = self.model if self.model else (setup_model if setup_model else "gemma-4-31b-it")
        
        if not self.api_key:
            raise Exception("API Key belum dikonfigurasi. Harap buka halaman setup Gemini SOC Assistant.")

    def stream(self, records):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.active_model}:generateContent?key={self.api_key}"
        
        for record in records:
            log_content = record.get(self.field, "")
            if log_content:
                payload = {
                    "contents": [{"parts": [{"text": f"{self.prompt}\n\nData:\n{log_content}"}]}]
                }
                req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
                try:
                    with urllib.request.urlopen(req, timeout=20) as response:
                        res_data = json.loads(response.read().decode('utf-8'))
                        record['gemini_analysis'] = res_data['candidates'][0]['content']['parts'][0]['text']
                except Exception as e:
                    record['gemini_analysis'] = f"Error: {str(e)}"
            yield record

if __name__ == "__main__":
    dispatch(GeminiAnalyzeCommand, sys.argv, sys.stdin, sys.stdout, __name__)