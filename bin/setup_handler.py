import splunk.admin as admin
import splunk.entity as entity

class GeminiSetupHandler(admin.MConfigHandler):
    def setup(self):
        if self.requestedAction == admin.ACTION_EDIT:
            for arg in ['api_key', 'model_name']:
                self.supportedArgs.addOptArg(arg)

    def handleList(self, confInfo):
        # Ambil model saat ini dari file conf
        confDict = self.readConf("gemini_settings")
        if confDict:
            for stanza, settings in confDict.items():
                for key, val in settings.items():
                    confInfo[stanza].append(key, val)

    def handleEdit(self, confInfo):
        name = self.callerArgs.id
        args = self.callerArgs
        
        # Simpan Model ke gemini_settings.conf
        if 'model_name' in args:
            self.writeConf('gemini_settings', 'gemini_config', {'model_name': args['model_name'][0]})
        
        # Simpan API Key ke Storage Passwords (Aman)
        if 'api_key' in args:
            api_key = args['api_key'][0]
            try:
                # Coba buat kredensial baru
                entity.createEntity('admin/passwords', {
                    'name': 'gemini_api_user',
                    'password': api_key,
                    'realm': 'gemini_soc_assistant_realm'
                }, sessionKey=self.getSessionKey())
            except Exception as e:
                # Jika sudah ada (Error EntityExists), lakukan UPDATE (Rotasi Key)
                try:
                    ent = entity.getEntity('admin/passwords', 'gemini_soc_assistant_realm:gemini_api_user', sessionKey=self.getSessionKey())
                    ent['password'] = api_key
                    entity.setEntity(ent, sessionKey=self.getSessionKey())
                except Exception as update_err:
                    raise Exception(f"Gagal memperbarui API Key: {str(update_err)}")

admin.init(GeminiSetupHandler, admin.CONTEXT_NONE)