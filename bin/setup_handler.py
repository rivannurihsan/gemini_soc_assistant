import splunk.admin as admin
import splunk.entity as entity

class GeminiSetupHandler(admin.MConfigHandler):
    def setup(self):
        # Menerima request baik sebagai Edit maupun Create
        if self.requestedAction in [admin.ACTION_EDIT, admin.ACTION_CREATE]:
            for arg in ['api_key', 'model_name', 'default_role']:
                self.supportedArgs.addOptArg(arg)

    def handleList(self, confInfo):
        confDict = self.readConf("gemini_settings")
        if confDict:
            for stanza, settings in confDict.items():
                for key, val in settings.items():
                    confInfo[stanza].append(key, val)

    def handleEdit(self, confInfo):
        args = self.callerArgs
        
        # Simpan Model & Role
        if 'model_name' in args and args['model_name'][0]:
            self.writeConf('gemini_settings', 'gemini_config', {'model_name': args['model_name'][0]})
            
        if 'default_role' in args and args['default_role'][0]:
            self.writeConf('gemini_settings', 'gemini_config', {'default_role': args['default_role'][0]})
        
        # Simpan API Key dengan aman (SHC Safe)
        if 'api_key' in args and args['api_key'][0] and args['api_key'][0] != '********':
            api_key = args['api_key'][0]
            try:
                entity.createEntity('admin/passwords', {
                    'name': 'gemini_api_user',
                    'password': api_key,
                    'realm': 'gemini_soc_assistant_realm'
                }, namespace='gemini_soc_assistant', owner='nobody', sessionKey=self.getSessionKey())
            except Exception as e:
                try:
                    ent = entity.getEntity('admin/passwords', 'gemini_soc_assistant_realm:gemini_api_user', namespace='gemini_soc_assistant', owner='nobody', sessionKey=self.getSessionKey())
                    ent['password'] = api_key
                    entity.setEntity(ent, sessionKey=self.getSessionKey())
                except Exception as update_err:
                    raise Exception(f"Gagal memperbarui API Key di Search Head: {str(update_err)} | (Create err: {str(e)})")

    # Duplikasi fungsi agar handleCreate menjalankan logika yang sama persis
    handleCreate = handleEdit

admin.init(GeminiSetupHandler, admin.CONTEXT_NONE)