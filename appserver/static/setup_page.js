require([
    "jquery",
    "splunkjs/mvc",
    "splunkjs/mvc/utils",
    "splunkjs/mvc/simplexml/ready!"
], function($, mvc, utils) {
    
    // Logika UI Dropdown
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

        $('#status_msg').css("color", "blue").text("Sedang menghubungi server Splunk...");
        
        // Membangun URL Absolut yang menembak langsung ke Core Splunkd
        var basePath = utils.make_url('/splunkd/__raw/servicesNS/nobody/gemini_soc_assistant/admin/gemini_setup/gemini_api_setup');

        // Fungsi 1: Mencoba melakukan UPDATE (Edit)
        function updateConfig() {
            $.ajax({
                url: basePath + '/gemini_config',
                type: 'POST',
                data: {
                    api_key: apiKey,
                    model_name: modelName
                },
                success: function() {
                    $('#status_msg').css("color", "green").text("Konfigurasi Berhasil Diperbarui!");
                    setTimeout(function(){ location.reload(); }, 2000);
                },
                error: function(xhr) {
                    // Jika Splunk bilang "404 Not Found" (belum ada), kita jalankan fungsi CREATE
                    if (xhr.status === 404) {
                        createConfig();
                    } else {
                        showError(xhr);
                    }
                }
            });
        }

        // Fungsi 2: Mencoba melakukan CREATE baru
        function createConfig() {
            $.ajax({
                url: basePath,
                type: 'POST',
                data: {
                    name: 'gemini_config', // Parameter name WAJIB saat Create di Splunk
                    api_key: apiKey,
                    model_name: modelName
                },
                success: function() {
                    $('#status_msg').css("color", "green").text("Konfigurasi Baru Berhasil Dibuat!");
                    setTimeout(function(){ location.reload(); }, 2000);
                },
                error: function(xhr) {
                    showError(xhr);
                }
            });
        }

        // Fungsi 3: Menangkap dan membedah Error Detail dari Backend
        function showError(xhr) {
            var errorMsg = "Unknown Error";
            try {
                // Mencoba mem-parsing response JSON bawaan Splunkd
                var responseJson = JSON.parse(xhr.responseText);
                if (responseJson && responseJson.messages && responseJson.messages.length > 0) {
                    errorMsg = responseJson.messages[0].text;
                }
            } catch(e) {
                // Fallback jika response bukan JSON
                errorMsg = xhr.responseText || xhr.statusText;
            }
            
            var finalOutput = "Gagal menyimpan: [HTTP " + xhr.status + "] " + errorMsg;
            $('#status_msg').css("color", "red").text(finalOutput);
            console.error("--- SPLUNK REST API ERROR DETAILS ---", xhr);
        }

        // Trigger pertama: Mulai dari mencoba Update
        updateConfig();
    });
});