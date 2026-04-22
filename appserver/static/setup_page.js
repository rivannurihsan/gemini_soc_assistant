require([
    "jquery",
    "splunkjs/mvc",
    "splunkjs/mvc/simplexml/ready!"
], function($, mvc) {
    var service = mvc.createService({ app: "gemini_soc_assistant", owner: "nobody" });
    const REALM = "gemini_soc_assistant_realm";
    const USER = "gemini_api_user";

    // 1. Inisialisasi Form & Masking
    function initSetup() {
        // Load API Key Status
        service.get("storage/passwords", { search: "realm=" + REALM }, function(err, resp) {
            if (resp && resp.data && resp.data.entry && resp.data.entry.length > 0) {
                $('#api_key_input').val("********").addClass("secure-mask");
                $('#key_info').text("Key sudah terkonfigurasi secara aman.").css("color", "green");
            }
        });

        // Load Model & Default Role
        service.get("properties/gemini_settings/gemini_config", {}, function(err, resp) {
            if (resp && resp.data) {
                $('#model_select').val(resp.data.model_name);
                loadRoles(resp.data.default_role);
            } else {
                loadRoles("soc_analyst");
            }
        });
    }

    // 2. Load Roles ke Dropdown
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
            if (selectedRole) dropdown.val(selectedRole);
        });
    }

    // 3. Tambah/Update Role
    $('#add_role_btn').on('click', function() {
        var rName = $('#new_role_name').val().trim().toLowerCase().replace(/\s+/g, '_');
        var rInst = $('#role_instructions').val();
        if(!rName || !rInst) return alert("Isi nama dan instruksi role!");

        service.post("configs/conf-gemini_settings", { name: "role:" + rName, instructions: rInst }, function(err, r) {
            if (err && err.status === 409) {
                service.post("properties/gemini_settings/role:" + rName, { instructions: rInst }, function() {
                    alert("Role diperbarui!"); loadRoles(rName);
                });
            } else {
                alert("Role berhasil disimpan!"); loadRoles(rName);
            }
        });
    });

    // 4. Simpan Konfigurasi Utama
    $('#save_btn').on('click', function() {
        var key = $('#api_key_input').val();
        var model = $('#model_select').val();
        var role = $('#default_role_select').val();

        $('#status_msg').css("color", "blue").text("Menyimpan...");

        service.post("properties/gemini_settings/gemini_config", { model_name: model, default_role: role }, function() {
            if (key !== "********" && key.trim() !== "") {
                var credId = encodeURIComponent(REALM + ":" + USER + ":");
                service.del("storage/passwords/" + credId, {}, function() {
                    service.post("storage/passwords", { name: USER, password: key, realm: REALM }, function() {
                        done();
                    });
                });
            } else { done(); }
        });
    });

    function done() {
        service.post("apps/local/gemini_soc_assistant", { configured: true }, function() {
            $('#status_msg').css("color", "green").text("Tersimpan! Memuat ulang...");
            setTimeout(function() { window.location.reload(); }, 1500);
        });
    }

    initSetup();
});