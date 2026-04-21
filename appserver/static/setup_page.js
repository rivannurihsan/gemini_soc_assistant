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

        $('#status_msg').text("Sedang menyimpan...");
        
        var service = mvc.createService();
        service.post("/services/gemini_setup/gemini_config", {
            api_key: apiKey,
            model_name: modelName
        }, function(err, response) {
            if (response) {
                $('#status_msg').css("color", "green").text("Konfigurasi Berhasil Disimpan!");
                setTimeout(function(){ location.reload(); }, 2000);
            } else {
                $('#status_msg').css("color", "red").text("Gagal menyimpan: " + err);
            }
        });
    });
});