require([
    "jquery",
    "splunkjs/mvc",
    "splunkjs/mvc/simplexml/ready!"
], function($, mvc) {
    
    var service = mvc.createService({ app: "gemini_soc_assistant", owner: "nobody" });

    // ==========================================
    // MUAT KONFIGURASI SAAT HALAMAN DIBUKA
    // ==========================================
    service.get("properties/gemini_settings/gemini_config", {}, function(err, response) {
        if (response && response.data) {
            var savedModel = response.data.model_name;
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
        }
        $('#api_key_input').attr('placeholder', '******** (Biarkan kosong jika tidak ingin mengubah API Key)');
    });

    // ==========================================
    // LOGIKA UI
    // ==========================================
    $('#model_select').on('change', function() {
        if ($(this).val() === 'custom') {
            $('#custom_model_div').show();
        } else {
            $('#custom_model_div').hide();
        }
    });

    // ==========================================
    // PROSES PENYIMPANAN
    // ==========================================
    $('#save_btn').on('click', function() {
        var apiKey = $('#api_key_input').val();
        var selectedModel = $('#model_select').val();
        var modelName = (selectedModel === 'custom') ? $('#custom_model_input').val() : selectedModel;
        
        if (!modelName) {
            alert("Harap pilih atau masukkan nama model.");
            return;
        }

        $('#status_msg').css("color", "blue").text("Menyimpan pengaturan ke Splunk...");

        // TAHAP 3: Fungsi untuk menandai aplikasi "Sudah Dikonfigurasi"
        function markAppAsConfigured() {
            $('#status_msg').text("Mendaftarkan status aplikasi...");
            
            // Endpoint ini mengubah is_configured=1 di local/app.conf
            service.post("apps/local/gemini_soc_assistant", {
                configured: true
            }, function(err, response) {
                $('#status_msg').css("color", "green").text("Aplikasi Siap Digunakan! Mengalihkan halaman...");
                
                // UX yang baik: Arahkan langsung ke halaman Panduan / Pencarian setelah selesai
                setTimeout(function(){ 
                    window.location.href = "user_guide"; 
                }, 1500);
            });
        }

        // TAHAP 1: Simpan Model
        service.post("properties/gemini_settings/gemini_config", {
            "model_name": modelName
        }, function(err, response) {
            if (err && err.status !== 200 && err.status !== 201) {
                var errMsg = err.errorText || err.statusText || "Unknown Error";
                $('#status_msg').css("color", "red").text("Gagal menyimpan Model: " + errMsg);
                return;
            }

            // TAHAP 2: Simpan API Key (Jika diisi user)
            if (apiKey && apiKey.trim() !== "") {
                $('#status_msg').text("Model tersimpan. Sedang mengamankan API Key...");
                var realmName = "gemini_soc_assistant_realm";
                var userName = "gemini_api_user";
                var credId = encodeURIComponent(realmName + ":" + userName + ":");

                service.del("storage/passwords/" + credId, {}, function() {
                    service.post("storage/passwords", {
                        name: userName,
                        password: apiKey,
                        realm: realmName
                    }, function(err2, resp2) {
                        if (err2 && err2.status !== 200 && err2.status !== 201) {
                            var errMsg2 = err2.errorText || err2.statusText || "Unknown Error";
                            $('#status_msg').css("color", "red").text("Gagal mengamankan API Key: " + errMsg2);
                        } else {
                            // Lanjut ke Tahap 3
                            markAppAsConfigured(); 
                        }
                    });
                });
            } else {
                // Lanjut ke Tahap 3 (jika API key tidak diubah)
                markAppAsConfigured(); 
            }
        });
    });
});