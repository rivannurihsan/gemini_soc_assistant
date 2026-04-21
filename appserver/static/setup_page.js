require([
    "jquery",
    "splunkjs/mvc",
    "splunkjs/mvc/simplexml/ready!"
], function($, mvc) {
    
    var service = mvc.createService({ app: "gemini_soc_assistant", owner: "nobody" });

    // 1. MUAT KONFIGURASI SAAT HALAMAN DIBUKA
    service.get("properties/gemini_settings/gemini_config", {}, function(err, response) {
        if (response && response.data) {
            var savedModel = response.data.model_name;
            var savedKey = response.data.api_key;

            if (savedModel) {
                var modelExists = $('#model_select option[value="' + savedModel + '"]').length > 0;
                if (modelExists) {
                    $('#model_select').val(savedModel);
                } else {
                    $('#model_select').val('custom');
                    $('#custom_model_div').show();
                    $('#custom_model_input').val(savedModel);
                }
            }
            
            if (savedKey && savedKey.trim() !== "") {
                $('#api_key_input').attr('placeholder', '******** (API Key sudah tersimpan. Kosongkan jika tidak ingin diubah)');
            } else {
                $('#api_key_input').attr('placeholder', 'Masukkan API Key Anda');
            }
        }
    });

    // 2. LOGIKA TAMPILAN DROPDOWN
    $('#model_select').on('change', function() {
        if ($(this).val() === 'custom') {
            $('#custom_model_div').show();
        } else {
            $('#custom_model_div').hide();
        }
    });

    // 3. PROSES SIMPAN LANGSUNG KE FILE CONF
    $('#save_btn').on('click', function() {
        var apiKey = $('#api_key_input').val();
        var selectedModel = $('#model_select').val();
        var modelName = (selectedModel === 'custom') ? $('#custom_model_input').val() : selectedModel;
        
        if (!modelName) {
            alert("Harap pilih atau masukkan nama model.");
            return;
        }

        $('#status_msg').css("color", "blue").text("Menyiapkan konfigurasi untuk Deployer...");

        // Siapkan payload untuk ditulis ke gemini_settings.conf
        var configPayload = { "model_name": modelName };
        if (apiKey && apiKey.trim() !== "") {
            configPayload["api_key"] = apiKey;
        }

        service.post("properties/gemini_settings/gemini_config", configPayload, function(err, response) {
            if (err && err.status !== 200 && err.status !== 201) {
                var errMsg = err.errorText || err.statusText || "Unknown Error";
                $('#status_msg').css("color", "red").text("Gagal menyimpan: " + errMsg);
                return;
            }

            $('#status_msg').text("Konfigurasi tersimpan! Mendaftarkan status aplikasi...");
            
            // Tandai aplikasi sebagai 'Configured'
            service.post("apps/local/gemini_soc_assistant", {
                configured: true
            }, function(err2, response2) {
                $('#status_msg').css("color", "green").text("Aplikasi Siap Di-Push ke Cluster! Mengalihkan halaman...");
                setTimeout(function(){ 
                    window.location.href = "user_guide"; 
                }, 1500);
            });
        });
    });
});