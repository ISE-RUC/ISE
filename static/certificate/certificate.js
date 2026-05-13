(function () {
    document.querySelectorAll(".certificate-row[data-href]").forEach(function (row) {
        row.addEventListener("click", function (event) {
            if (event.target.closest("a, button, form, input, textarea, label")) {
                return;
            }
            window.location.href = row.getAttribute("data-href");
        });
    });

    function getCsrfToken() {
        const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (input) {
            return input.value;
        }
        const match = document.cookie.match(/(?:^|; )csrftoken=([^;]+)/);
        return match ? decodeURIComponent(match[1]) : "";
    }

    function showApiMessage(message, isError) {
        if (!message) {
            return;
        }
        const list = document.querySelector(".messages") || document.createElement("ul");
        if (!list.classList.contains("messages")) {
            list.className = "messages";
            const main = document.querySelector("main");
            if (main) {
                main.prepend(list);
            }
        }
        const item = document.createElement("li");
        item.className = isError ? "error" : "success";
        item.textContent = message;
        list.prepend(item);
    }

    async function postJson(url, payload) {
        const response = await fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken()
            },
            credentials: "same-origin",
            body: JSON.stringify(payload || {})
        });
        return response.json();
    }

    document.querySelectorAll("form[data-api-form]").forEach(function (form) {
        form.addEventListener("submit", async function (event) {
            event.preventDefault();
            const submitButton = form.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = true;
            }
            const formData = new FormData(form);
            const payload = {
                certificate_type: formData.get("certificate_type") || "party-member",
                purpose: formData.get("purpose") || "",
                attachment_note: formData.get("attachment_note") || ""
            };

            try {
                const result = await postJson(form.dataset.apiUrl, payload);
                showApiMessage(result.msg, result.code !== 0);
                if (result.data && result.data.detail_url) {
                    window.location.href = result.data.detail_url;
                }
            } catch (error) {
                showApiMessage("请求失败，请稍后重试。", true);
            } finally {
                if (submitButton) {
                    submitButton.disabled = false;
                }
            }
        });
    });

    document.querySelectorAll("form[data-api-action]").forEach(function (form) {
        form.addEventListener("submit", async function (event) {
            event.preventDefault();
            const submitButton = form.querySelector('button[type="submit"]');
            if (submitButton) {
                submitButton.disabled = true;
            }
            try {
                const result = await postJson(form.dataset.apiUrl, {});
                showApiMessage(result.msg, result.code !== 0);
                if (result.data && result.data.detail_url) {
                    window.location.href = result.data.detail_url;
                }
            } catch (error) {
                showApiMessage("请求失败，请稍后重试。", true);
            } finally {
                if (submitButton) {
                    submitButton.disabled = false;
                }
            }
        });
    });

    const profileModal = document.getElementById("profileModal");
    const previewModal = document.getElementById("previewModal");
    const previewButton = document.getElementById("openPreviewModal");
    const reopenProfileButton = document.getElementById("reopenProfileModal");
    const radios = document.querySelectorAll('input[name="certificate_type"]');
    const selectedCertificateName = document.getElementById("selectedCertificateName");
    const statusCertificateName = document.getElementById("statusCertificateName");
    const previewTypePill = document.getElementById("previewTypePill");
    const previewCertificateTitle = document.getElementById("previewCertificateTitle");
    const previewDescription = document.getElementById("previewDescription");
    const previewName = document.getElementById("previewName");
    const previewStudentId = document.getElementById("previewStudentId");
    const previewMajor = document.getElementById("previewMajor");
    const previewGender = document.getElementById("previewGender");
    const profileName = document.querySelector("[data-profile-name]");
    const profileId = document.querySelector("[data-profile-id]");
    const profileMajor = document.querySelector("[data-profile-major]");
    const profileGender = document.querySelector("[data-profile-gender]");

    const student = {
        name: profileName ? profileName.textContent.trim() : "",
        studentId: profileId ? profileId.textContent.trim() : "",
        major: profileMajor ? profileMajor.textContent.trim() : "",
        gender: profileGender ? profileGender.textContent.trim() : ""
    };

    function showModal(modal) {
        if (modal) {
            modal.classList.add("is-visible");
        }
    }

    function hideModal(modal) {
        if (modal) {
            modal.classList.remove("is-visible");
        }
    }

    function updatePreview() {
        const selected = document.querySelector('input[name="certificate_type"]:checked');
        if (!selected) {
            return;
        }

        const cardName = selected.dataset.certificateName || "";
        const previewTitle = selected.dataset.previewTitle || cardName;

        if (selectedCertificateName) {
            selectedCertificateName.textContent = cardName;
        }
        if (statusCertificateName) {
            statusCertificateName.textContent = cardName;
        }
        if (previewTypePill) {
            previewTypePill.textContent = previewTitle;
        }
        if (previewCertificateTitle) {
            previewCertificateTitle.textContent = previewTitle;
        }
        if (previewName) {
            previewName.textContent = student.name;
        }
        if (previewStudentId) {
            previewStudentId.textContent = student.studentId;
        }
        if (previewMajor) {
            previewMajor.textContent = student.major;
        }
        if (previewGender) {
            previewGender.textContent = student.gender;
        }
        if (previewDescription) {
            previewDescription.textContent = "该生当前申请开具《" + previewTitle + "》，请以正式签发文件为准。";
        }
    }

    radios.forEach(function (radio) {
        radio.addEventListener("change", updatePreview);
    });

    document.querySelectorAll("[data-close-modal]").forEach(function (button) {
        button.addEventListener("click", function () {
            const targetId = button.getAttribute("data-close-modal");
            hideModal(document.getElementById(targetId));
        });
    });

    [profileModal, previewModal].forEach(function (modal) {
        if (!modal) {
            return;
        }
        modal.addEventListener("click", function (event) {
            if (event.target === modal) {
                hideModal(modal);
            }
        });
    });

    if (previewButton) {
        previewButton.addEventListener("click", function () {
            updatePreview();
            if (previewButton.dataset.pdfPreviewUrl) {
                const selected = document.querySelector('input[name="certificate_type"]:checked');
                const purpose = document.getElementById("purpose");
                const params = new URLSearchParams({
                    certificate_type: selected ? selected.value : "party-member",
                    purpose: purpose ? purpose.value : ""
                });
                window.open(previewButton.dataset.pdfPreviewUrl + "?" + params.toString(), "_blank", "noopener");
                return;
            }
            showModal(previewModal);
        });
    }

    if (reopenProfileButton) {
        reopenProfileButton.addEventListener("click", function () {
            showModal(profileModal);
        });
    }

    updatePreview();

    if (profileModal && reopenProfileButton) {
        showModal(profileModal);
    }
})();
