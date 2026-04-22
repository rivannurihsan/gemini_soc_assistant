require([
    "jquery",
    "splunkjs/mvc",
    "splunkjs/mvc/simplexml/ready!"
], function($, mvc) {
    var service = mvc.createService({ app: "gemini_soc_assistant", owner: "nobody" });
    const REALM = "gemini_soc_assistant_realm";
    const USER = "gemini_api_user";

    // 1. Inisialisasi Form & Load Konfigurasi Tersimpan
    function initSetup() {
        // Cek API Key
        service.get("storage/passwords", { search: "realm=" + REALM }, function(err, resp) {
            if (resp && resp.data && resp.data.entry && resp.data.entry.length > 0) {
                $('#api_key_input').val("********");
                $('#key_info').text("✓ Key terkonfigurasi & tersimpan aman.").css("color", "green");
            }
        });

        // Cek Model & Role menggunakan endpoint 'configs/conf-gemini_settings' yang lebih stabil
        service.get("configs/conf-gemini_settings/gemini_config", {}, function(err, resp) {
            var roleToSet = "soc_analyst"; // Fallback awal
            
            if (resp && resp.data && resp.data.entry && resp.data.entry.length > 0) {
                var content = resp.data.entry[0].content;
                var savedModel = content.model_name;
                
                if (savedModel) {
                    var isStandardModel = $('#model_select option').filter(function() { 
                        return $(this).val() === savedModel; 
                    }).length > 0;

                    if (isStandardModel) {
                        $('#model_select').val(savedModel);
                        $('#custom_model_div').hide();
                    } else {
                        $('#model_select').val("custom");
                        $('#custom_model_input').val(savedModel);
                        $('#custom_model_div').show();
                    }
                }
                
                if (content.default_role) {
                    roleToSet = content.default_role;
                }
            }
            loadRoles(roleToSet);
        });
    }

    // 2. Tampilkan/Sembunyikan Input Model Custom dinamis
    $('#model_select').on('change', function() {
        if ($(this).val() === 'custom') {
            $('#custom_model_div').show();
        } else {
            $('#custom_model_div').hide();
        }
    });

    // 3. Load Daftar Roles
    function loadRoles(selectedRole) {
        service.get("configs/conf-gemini_settings", {}, function(err, resp) {
            var dropdown = $('#default_role_select');
            dropdown.empty();
            
            if (resp && resp.data && resp.data.entry) {
                resp.data.entry.forEach(function(e) {
                    if (e.name.startsWith("role:")) {
                        var rName = e.name.split(":")[1];
                        dropdown.append($('<option>').val(rName).text(rName));
                    }
                });
            }
            
            if (selectedRole) {
                dropdown.val(selectedRole);
            }
        });
    }

    // 4. Tambah/Update Role (Tahan terhadap Error 409)
    $('#add_role_btn').on('click', function() {
        var rName = $('#new_role_name').val().trim().toLowerCase().replace(/\s+/g, '_');
        var rInst = $('#role_instructions').val();
        if(!rName || !rInst) return alert("Harap isi nama role dan instruksi sistemnya!");

        var roleStanza = "role:" + rName;
        $('#status_msg').css("color", "blue").text("Menyimpan Role...");
        
        // Coba buat baru
        service.post("configs/conf-gemini_settings", { name: roleStanza, instructions: rInst }, function(err, r) {
            if (err && err.status === 409) {
                // Jika sudah ada (409 Conflict), lakukan Update
                service.post("configs/conf-gemini_settings/" + roleStanza, { instructions: rInst }, function(err2, r2) {
                    if (!err2) {
                        $('#status_msg').css("color", "green").text("Role berhasil diperbarui!");
                        loadRoles(rName);
                    } else {
                        $('#status_msg').css("color", "red").text("Gagal memperbarui role: " + err2.status);
                    }
                });
            } else if (!err) {
                $('#status_msg').css("color", "green").text("Role baru berhasil disimpan!");
                loadRoles(rName);
            } else {
                $('#status_msg').css("color", "red").text("Gagal menyimpan role: " + err.status);
            }
            setTimeout(function() { $('#status_msg').text(""); }, 3000);
        });
    });

    // 5. Simpan Konfigurasi Utama (Tahan terhadap Error 404)
    $('#save_btn').on('click', function() {
        var key = $('#api_key_input').val();
        var selectedDropdownModel = $('#model_select').val();
        var finalModel = (selectedDropdownModel === 'custom') ? $('#custom_model_input').val().trim() : selectedDropdownModel;
        var finalRole = $('#default_role_select').val();

        if (!finalModel) return alert("Silakan pilih atau ketik nama model AI Anda!");

        $('#status_msg').css("color", "blue").text("Menyimpan konfigurasi ke server...");

        var payload = { model_name: finalModel, default_role: finalRole };

        // Fungsi lanjutan untuk menyimpan API Key
        function saveApiKeyAndFinish() {
            if (key && key !== "********" && key.trim() !== "") {
                var credId = encodeURIComponent(REALM + ":" + USER + ":");
                service.del("storage/passwords/" + credId, {}, function() {
                    service.post("storage/passwords", { name: USER, password: key, realm: REALM }, function(errKey, respKey) {
                        if (errKey) {
                            $('#status_msg').css("color", "red").text("Konfigurasi tersimpan, tapi gagal menyimpan API Key.");
                        } else {
                            done();
                        }
                    });
                });
            } else { 
                done(); 
            }
        }

        // Coba Update konfigurasi yang ada
        service.post("configs/conf-gemini_settings/gemini_config", payload, function(err, resp) {
            if (err && err.status === 404) {
                // Jika tidak ditemukan (404), paksa Buat Baru
                payload.name = "gemini_config";
                service.post("configs/conf-gemini_settings", payload, function(err2, resp2) {
                    if (err2) {
                        $('#status_msg').css("color", "red").text("Gagal membuat konfigurasi baru. Status " + err2.status);
                    } else {
                        saveApiKeyAndFinish();
                    }
                });
            } else if (err) {
                $('#status_msg').css("color", "red").text("Gagal menyimpan konfigurasi. Status " + err.status);
            } else {
                // Jika update sukses
                saveApiKeyAndFinish();
            }
        });
    });

    function done() {
        service.post("apps/local/gemini_soc_assistant", { configured: true }, function() {
            $('#status_msg').css("color", "green").text("✓ Konfigurasi Tersimpan! Memuat ulang halaman...");
            setTimeout(function() { window.location.reload(); }, 1500);
        });
    }

    // Jalankan skrip saat siap
    initSetup();
});