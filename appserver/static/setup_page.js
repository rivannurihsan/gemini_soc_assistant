require([
    "jquery",
    "splunkjs/mvc",
    "splunkjs/mvc/simplexml/ready!"
], function($, mvc) {
    var service = mvc.createService({ app: "gemini_soc_assistant", owner: "nobody" });
    const REALM = "gemini_soc_assistant_realm";
    const USER = "gemini_api_user";

    // --- FUNGSI LOAD DATA AWAL ---
    function initializeSetup() {
        // 1. Muat Model & Role dari file konfigurasi lokal Search Head
        service.get("properties/gemini_settings/gemini_config", {}, function(err, resp) {
            if (resp && resp.data) {
                if (resp.data.model_name) {
                    $('#model_select').val(resp.data.model_name);
                }
                loadRoles(resp.data.default_role || "default");
            } else {
                loadRoles("default");
            }
        });

        // 2. Cek apakah API Key sudah tersimpan di Credential Store
        service.get("storage/passwords", { search: "realm=" + REALM }, function(err, resp) {
            if (resp && resp.data && resp.data.entry && resp.data.entry.length > 0) {
                $('#api_key_input').val("********").attr("disabled", false);
                $('#key_status_label').text("(Telah Terkonfigurasi)").css("color", "green");
            }
        });
    }

    // --- FUNGSI LOAD & UPDATE ROLE ---
    function loadRoles(selectedRole) {
        service.get("configs/conf-gemini_settings", {}, function(err, resp) {
            var roleDropdown = $('#default_role_select');
            roleDropdown.empty().append('<option value="default">default (Tanpa Instruksi Khusus)</option>');
            
            if (resp && resp.data && resp.data.entry) {
                resp.data.entry.forEach(function(e) {
                    if (e.name.startsWith("role:")) {
                        var rName = e.name.split(":")[1];
                        roleDropdown.append($('<option>').val(rName).text(rName));
                    }
                });
            }
            if (selectedRole) roleDropdown.val(selectedRole);
        });
    }

    $('#add_role_btn').on('click', function() {
        var name = $('#new_role_name').val().trim().toLowerCase().replace(/\s+/g, '_');
        var inst = $('#role_instructions').val();
        if(!name || !inst) return alert("Harap isi Nama Role dan Instruksi Sistem!");

        $('#role_status').text("Menyimpan role...").css("color", "blue");
        
        service.post("configs/conf-gemini_settings", { name: "role:" + name, instructions: inst }, function(err, r) {
            // Jika role sudah ada (Error 409), maka lakukan update
            if (err && err.status === 409) {
                service.post("properties/gemini_settings/role:" + name, { instructions: inst }, function() {
                    $('#role_status').text("Role berhasil diperbarui!").css("color", "green");
                    $('#new_role_name').val(''); $('#role_instructions').val('');
                    loadRoles(name);
                });
            } else {
                $('#role_status').text("Role baru berhasil ditambahkan!").css("color", "green");
                $('#new_role_name').val(''); $('#role_instructions').val('');
                loadRoles(name);
            }
            setTimeout(function() { $('#role_status').text(""); }, 3000);
        });
    });

    // --- LOGIKA SIMPAN UTAMA ---
    $('#save_btn').on('click', function() {
        var key = $('#api_key_input').val();
        var model = $('#model_select').val();
        var role = $('#default_role_select').val();

        $('#status_msg').css("color", "blue").text("Menyimpan konfigurasi...");

        // A. Simpan perubahan Model & Role ke file conf di Search Head
        service.post("properties/gemini_settings/gemini_config", { 
            model_name: model, 
            default_role: role 
        }, function() {
            
            // B. Jika API Key diubah oleh user (bukan ********), perbarui Credential Store
            if (key && key !== "********" && key.trim() !== "") {
                var credId = encodeURIComponent(REALM + ":" + USER + ":");
                service.del("storage/passwords/" + credId, {}, function() {
                    service.post("storage/passwords", { name: USER, password: key, realm: REALM }, function() {
                        finishConfig();
                    });
                });
            } else {
                // Jika user tidak mengganti API Key, langsung sukses
                finishConfig();
            }
        });
    });

    function finishConfig() {
        service.post("apps/local/gemini_soc_assistant", { configured: true }, function() {
            $('#status_msg').css("color", "green").text("Semua Perubahan Berhasil Disimpan!");
            setTimeout(function() { window.location.reload(); }, 1500);
        });
    }

    // Jalankan fungsi load saat halaman siap
    initializeSetup();
});