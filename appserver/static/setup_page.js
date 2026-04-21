require([
    "splunkjs/mvc",
    "splunkjs/mvc/simplexml/ready!"
], function(mvc) {
    
    // Logika menampilkan input kustom jika opsi "custom" dipilih
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
        
        // Jika pilih kustom, ambil nilai dari input teks
        var modelName = (selectedModel === 'custom') ? $('#custom_model_input').val() : selectedModel;
        
        if (!modelName) {
            alert("Harap pilih atau masukkan nama model.");
            return;
        }

        $('#status_msg').css("color", "blue").text("Sedang menyimpan...");
        
        var service = mvc.createService();
        
        // PERBAIKAN: URL endpoint diubah agar sesuai dengan restmap.conf yang baru
        service.post("/services/gemini_setup/gemini_api_setup", {
            api_key: apiKey,
            model_name: modelName
        }, function(err, response) {
            if (response) {
                $('#status_msg').css("color", "green").text("Konfigurasi Berhasil Disimpan!");
                setTimeout(function(){ location.reload(); }, 2000);
            } else {
                // PERBAIKAN: Parsing objek error agar terbaca manusia
                var errorMsg = "Unknown Error";
                if (err && err.data && err.data.messages && err.data.messages.length > 0) {
                    errorMsg = err.data.messages[0].text;
                } else if (err && err.statusText) {
                    errorMsg = err.status + " " + err.statusText;
                } else {
                    errorMsg = JSON.stringify(err);
                }
                
                $('#status_msg').css("color", "red").text("Gagal menyimpan: " + errorMsg);
            }
        });
    });
});