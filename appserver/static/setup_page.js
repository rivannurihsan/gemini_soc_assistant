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

        // Cek Model & Role
        service.get("properties/gemini_settings/gemini_config", {}, function(err, resp) {
            var roleToSet = "soc_analyst"; // Fallback awal
            
            if (resp && resp.data) {
                var savedModel = resp.data.model_name;
                
                if (savedModel) {
                    // Periksa apakah model yang tersimpan ada di dalam daftar <select> standar
                    var isStandardModel = $('#model_select option').filter(function() { 
                        return $(this).val() === savedModel; 
                    }).length > 0;

                    if (isStandardModel) {
                        $('#model_select').val(savedModel);
                        $('#custom_model_div').hide();
                    } else {
                        // Jika tidak ada di daftar, otomatis pilih custom dan tampilkan text input-nya
                        $('#model_select').val("custom");
                        $('#custom_model_input').val(savedModel);
                        $('#custom_model_div').show();
                    }
                }
                
                // Set default role jika ada
                if (resp.data.default_role) {
                    roleToSet = resp.data.default_role;
                }
            }
            // Panggil fungsi loadRoles dan wajibkan ia memilih 'roleToSet' setelah memuat list
            loadRoles(roleToSet);
        });
    }

    // 2. Tampilkan/Sembunyikan Input Model Custom secara dinamis
    $('#model_select').on('change', function() {
        if ($(this).val() === 'custom') {
            $('#custom_model_div').show();
        } else {
            $('#custom_model_div').hide();
        }
    });

    // 3. Load Daftar Roles dari file .conf
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
            
            // Pilih role yang tersimpan di backend
            if (selectedRole) {
                dropdown.val(selectedRole);
            }
        });
    }

    // 4. Tambah/Update Role
    $('#add_role_btn').on('click', function() {
        var rName = $('#new_role_name').val().trim().toLowerCase().replace(/\s+/g, '_');
        var rInst = $('#role_instructions').val();
        if(!rName || !rInst) return alert("Harap isi nama role dan instruksi sistemnya!");

        service.post("configs/conf-gemini_settings", { name: "role:" + rName, instructions: rInst }, function(err, r) {
            if (err && err.status === 409) {
                service.post("properties/gemini_settings/role:" + rName, { instructions: rInst }, function() {
                    alert("Role berhasil diperbarui!"); 
                    loadRoles(rName); // Refresh dropdown
                });
            } else {
                alert("Role baru berhasil disimpan!"); 
                loadRoles(rName); // Refresh dropdown
            }
        });
    });

    // 5. Simpan Konfigurasi Utama
    $('#save_btn').on('click', function() {
        var key = $('#api_key_input').val();
        
        // Cek model mana yang dipilih (Dropdown biasa atau Input Custom)
        var selectedDropdownModel = $('#model_select').val();
        var finalModel = (selectedDropdownModel === 'custom') ? $('#custom_model_input').val().trim() : selectedDropdownModel;
        
        var finalRole = $('#default_role_select').val();

        if (!finalModel) return alert("Silakan pilih atau ketik nama model AI Anda!");

        $('#status_msg').css("color", "blue").text("Menyimpan ke server...");

        // Simpan Model & Role
        service.post("properties/gemini_settings/gemini_config", { 
            model_name: finalModel, 
            default_role: finalRole 
        }, function(err, resp) {
            
            // Simpan API Key jika tidak termasking
            if (key && key !== "********" && key.trim() !== "") {
                var credId = encodeURIComponent(REALM + ":" + USER + ":");
                service.del("storage/passwords/" + credId, {}, function() {
                    service.post("storage/passwords", { name: USER, password: key, realm: REALM }, function() {
                        done();
                    });
                });
            } else { 
                done(); 
            }
        });
    });

    function done() {
        service.post("apps/local/gemini_soc_assistant", { configured: true }, function() {
            $('#status_msg').css("color", "green").text("✓ Tersimpan! Memuat ulang halaman...");
            setTimeout(function() { window.location.reload(); }, 1500);
        });
    }

    // Jalankan skrip saat siap
    initSetup();
});