require([
    "splunkjs/mvc",
    "splunkjs/mvc/simplexml/ready!"
], function(mvc) {
    
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

        $('#status_msg').css("color", "blue").text("Sedang menyimpan...");
        
        // Buat service instance khusus untuk aplikasi kita
        var service = mvc.createService({ app: "gemini_soc_assistant", owner: "nobody" });
        
        // PERBAIKAN: Gunakan relative path. SDK otomatis mengubahnya menjadi /servicesNS/nobody/gemini_soc_assistant/admin/...
        var endpointPath = "admin/gemini_setup/gemini_api_setup/gemini_config";
        
        service.post(endpointPath, {
            api_key: apiKey,
            model_name: modelName
        }, function(err, response) {
            if (response) {
                $('#status_msg').css("color", "green").text("Konfigurasi Berhasil Disimpan!");
                setTimeout(function(){ location.reload(); }, 2000);
            } else {
                // LOGIKA DEBUGGING DETAIL UNTUK SOC DEVELOPER
                console.error("--- SPLUNK REST API ERROR DETAILS ---");
                console.error(err);
                
                var errorMsg = "Terjadi Kesalahan Tidak Dikenal.";
                var httpStatus = err.status || "Unknown Status";
                
                // Coba ekstrak pesan error langsung dari response Splunkd
                if (err && err.data && err.data.messages && err.data.messages.length > 0) {
                    errorMsg = err.data.messages[0].text;
                } else if (err && err.errorText) {
                    errorMsg = err.errorText;
                } else if (err && err.statusText) {
                    errorMsg = err.statusText;
                }

                // Tampilkan di UI dengan format: [HTTP Status] - [Pesan Detail]
                var finalOutput = "Gagal menyimpan: [" + httpStatus + "] " + errorMsg;
                $('#status_msg').css("color", "red").text(finalOutput);
                
                // Tambahkan hint untuk developer
                $('#status_msg').append("<br/><small><i>*Cek Developer Console (F12) untuk log error mentah.</i></small>");
            }
        });
    });
});