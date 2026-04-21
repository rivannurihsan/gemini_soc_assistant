require([
    "jquery",
    "splunkjs/mvc",
    "splunkjs/mvc/simplexml/ready!"
], function($, mvc) {
    
    var service = mvc.createService({ app: "gemini_soc_assistant", owner: "nobody" });

    // ==========================================
    // FITUR BARU: MUAT KONFIGURASI SAAT HALAMAN DIBUKA
    // ==========================================
    service.get("properties/gemini_settings/gemini_config", {}, function(err, response) {
        if (response && response.data) {
            var savedModel = response.data.model_name;
            
            if (savedModel) {
                // Cek apakah model yang tersimpan ada di opsi dropdown standar kita
                var modelExists = $('#model_select option[value="' + savedModel + '"]').length > 0;
                
                if (modelExists) {
                    $('#model_select').val(savedModel); // Pilih otomatis
                } else {
                    // Jika itu model kustom, tampilkan kotak input teksnya
                    $('#model_select').val('custom');
                    $('#custom_model_div').show();
                    $('#custom_model_input').val(savedModel);
                }
            }
        }
        
        // Ubah teks bantuan di kolom API Key untuk keamanan
        $('#api_key_input').attr('placeholder', '******** (Biarkan kosong jika tidak ingin mengubah API Key)');
    });


    // ==========================================
    // LOGIKA UI & PENYIMPANAN
    // ==========================================
    $('#model_select').on('change', function() {
        if ($(this).val() === 'custom') {
            $('#custom_model_div').show();
        } else {
            $('#custom_model_div').hide();
        }
    });

    $('#save_btn').on('click', function() {
        var apiKey = $('#api_key_input').val();
        var selectedModel = $('#model_select').val();
        var modelName = (selectedModel === 'custom') ? $('#custom_model_input').val() : selectedModel;
        
        if (!modelName) {
            alert("Harap pilih atau masukkan nama model.");
            return;
        }

        $('#status_msg').css("color", "blue").text("Menyimpan pengaturan ke Splunk...");
        
        // TAHAP 1: Simpan Model ke gemini_settings.conf
        service.post("properties/gemini_settings/gemini_config", {
            "model_name": modelName
        }, function(err, response) {
            if (err && err.status !== 200 && err.status !== 201) {
                var errMsg = err.errorText || err.statusText || "Unknown Error";
                $('#status_msg').css("color", "red").text("Gagal menyimpan Model: " + errMsg);
                console.error("Error Model:", err);
                return;
            }

            // TAHAP 2: Simpan API Key (HANYA JIKA KOLOM DIISI OLEH USER)
            if (apiKey && apiKey.trim() !== "") {
                $('#status_msg').text("Model tersimpan. Sedang mengamankan API Key...");
                
                var realmName = "gemini_soc_assistant_realm";
                var userName = "gemini_api_user";
                var credId = encodeURIComponent(realmName + ":" + userName + ":");

                // Hapus kredensial lama terlebih dahulu
                service.del("storage/passwords/" + credId, {}, function() {
                    
                    // Simpan yang baru
                    service.post("storage/passwords", {
                        name: userName,
                        password: apiKey,
                        realm: realmName
                    }, function(err2, resp2) {
                        if (err2 && err2.status !== 200 && err2.status !== 201) {
                            var errMsg2 = err2.errorText || err2.statusText || "Unknown Error";
                            $('#status_msg').css("color", "red").text("Gagal mengamankan API Key: " + errMsg2);
                        } else {
                            $('#status_msg').css("color", "green").text("Model & API Key Baru Berhasil Disimpan!");
                            setTimeout(function(){ location.reload(); }, 2000);
                        }
                    });
                });
            } else {
                // Jika kolom API Key kosong, berarti user hanya ingin mengganti Model saja
                $('#status_msg').css("color", "green").text("Model Berhasil Diperbarui! (API Key tidak diubah)");
                setTimeout(function(){ location.reload(); }, 2000);
            }
        });
    });
});