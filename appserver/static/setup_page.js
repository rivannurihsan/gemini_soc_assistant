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
            loadRolesForManagement();
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

    function loadRolesForManagement() {
        service.get("configs/conf-gemini_settings", {}, function(err, resp) {
            var tbody = $('#role_management_table tbody');
            tbody.empty();
            if (resp && resp.data && resp.data.entry) {
                resp.data.entry.forEach(function(e) {
                    if (e.name.startsWith("role:")) {
                        var rName = e.name.split(":")[1];
                        var instructions = e.content.instructions || "";
                        var snippet = instructions.length > 90 ? instructions.substring(0, 90) + "..." : instructions;
                        
                        var tr = $('<tr>').css('border-bottom', '1px solid #2a4a5a');
                        tr.append($('<td>').css({'padding':'12px','color':'#7ec8e3'}).text(rName));
                        tr.append($('<td>').css('padding','12px').text(snippet));
                        
                        var actionTd = $('<td>').css('padding','12px');
                        var editBtn = $('<button>').text('✏️ Edit').css({'padding':'4px 8px','margin-right':'8px','background':'#2c5364','color':'#fff','border':'none','border-radius':'3px','cursor':'pointer'})
                            .on('click', function(evt) {
                                evt.preventDefault();
                                $('#form_title').text('✏️ Edit Role: ' + rName);
                                $('#new_role_name').val(rName).prop('readonly', true).css('opacity', '0.6');
                                $('#role_instructions').val(instructions);
                            });
                            
                        var delBtn = $('<button>').text('🗑️ Hapus').css({'padding':'4px 8px','background':'#ef476f','color':'#fff','border':'none','border-radius':'3px','cursor':'pointer'})
                            .on('click', function(evt) {
                                evt.preventDefault();
                                if(confirm("Yakin ingin menghapus role '" + rName + "'?")) {
                                    service.del("configs/conf-gemini_settings/" + e.name, {}, function(errDel) {
                                        if(!errDel) {
                                            $('#status_msg').css("color", "green").text("Role " + rName + " dihapus!");
                                            loadRolesForManagement();
                                            loadRoles(); // refresh dropdown
                                            setTimeout(function() { $('#status_msg').text(""); }, 3000);
                                        } else {
                                            alert("Gagal menghapus: " + errDel.status);
                                        }
                                    });
                                }
                            });
                        
                        actionTd.append(editBtn).append(delBtn);
                        tr.append(actionTd);
                        tbody.append(tr);
                    }
                });
            }
        });
    }

    function resetFormAndReload(rName) {
        $('#new_role_name').val('').prop('readonly', false).css('opacity', '1');
        $('#role_instructions').val('');
        $('#form_title').text('➕ Buat / Edit Role');
        loadRoles(rName);
        loadRolesForManagement();
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
                        resetFormAndReload(rName);
                    } else {
                        $('#status_msg').css("color", "red").text("Gagal memperbarui role: " + err2.status);
                    }
                });
            } else if (!err) {
                $('#status_msg').css("color", "green").text("Role baru berhasil disimpan!");
                resetFormAndReload(rName);
            } else {
                $('#status_msg').css("color", "red").text("Gagal menyimpan role: " + err.status);
            }
            setTimeout(function() { $('#status_msg').text(""); }, 3000);
        });
    });

    // 5. Simpan Konfigurasi Utama (Upsert Mode)
    $('#save_btn').on('click', function() {
        var key = $('#api_key_input').val();
        var selectedDropdownModel = $('#model_select').val();
        var finalModel = (selectedDropdownModel === 'custom') ? $('#custom_model_input').val().trim() : selectedDropdownModel;
        var finalRole = $('#default_role_select').val();

        if (!finalModel) return alert("Silakan pilih atau ketik nama model AI Anda!");

        $('#status_msg').css("color", "blue").text("Menyimpan konfigurasi...");

        var confPayload = { model_name: finalModel, default_role: finalRole };

        // Fungsi Helper untuk Upsert Config
        function upsertConfig(cb) {
            service.post("configs/conf-gemini_settings/gemini_config", confPayload, function(err, resp) {
                if (err && err.status === 404) {
                    confPayload.name = "gemini_config";
                    service.post("configs/conf-gemini_settings", confPayload, function(cerr, cresp) {
                        cb(cerr);
                    });
                } else {
                    cb(err);
                }
            });
        }

        // Fungsi Helper untuk Upsert API Key
        function upsertApiKey(cb) {
            if (key && key !== "********" && key.trim() !== "") {
                service.post("storage/passwords", { name: "gemini_api_user", password: key, realm: "gemini_soc_assistant_realm" }, function(perr, presp) {
                    if (perr && perr.status === 409) {
                        service.post("storage/passwords/gemini_soc_assistant_realm%3Agemini_api_user", { password: key }, function(uerr, uresp) {
                            cb(uerr);
                        });
                    } else {
                        cb(perr);
                    }
                });
            } else {
                cb(null); // Tidak ada perubahan key
            }
        }

        // Eksekusi Berantai
        upsertConfig(function(errConf) {
            if (errConf) {
                var msg = errConf.error || errConf.status || "Unknown Error";
                $('#status_msg').css("color", "red").text("Gagal menyimpan pengaturan model/role: " + msg);
                return;
            }
            
            upsertApiKey(function(errKey) {
                if (errKey) {
                    var msg = errKey.error || errKey.status || "Unknown Error";
                    $('#status_msg').css("color", "red").text("Gagal menyimpan API Key: " + msg);
                    return;
                }
                
                done();
            });
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