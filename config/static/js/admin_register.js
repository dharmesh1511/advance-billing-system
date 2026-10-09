/**
 * Admin Registration Frontend JS
 * Handles password toggling, client-side validation, and DRF API submission.
 */

document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('admin-register-form');
    if (!form) return;

    // Field references
    const firstNameInput = document.getElementById('first_name');
    const lastNameInput = document.getElementById('last_name');
    const usernameInput = document.getElementById('username');
    const emailInput = document.getElementById('email');
    const passwordInput = document.getElementById('password');
    const confirmPasswordInput = document.getElementById('confirm_password');

    // Toggle Buttons
    const togglePasswordBtn = document.getElementById('toggle-password-btn');
    const toggleConfirmPasswordBtn = document.getElementById('toggle-confirm-password-btn');

    // UI Feedback elements
    const submitBtn = document.getElementById('submit-btn');
    const btnText = document.getElementById('btn-text');
    const btnSpinner = document.getElementById('btn-spinner');
    const successAlert = document.getElementById('form-success-alert');
    const errorAlert = document.getElementById('form-error-alert');
    const successText = document.getElementById('success-text');
    const errorText = document.getElementById('error-text');

    // Helper: CSRF Cookie Extractor
    function getCsrfToken() {
        const csrfInput = document.querySelector('input[name="csrfmiddlewaretoken"]');
        if (csrfInput && csrfInput.value) {
            return csrfInput.value;
        }
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, 10) === ('csrftoken=')) {
                    cookieValue = decodeURIComponent(cookie.substring(10));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Helper: Password Visibility Toggle
    function setupPasswordToggle(inputEl, btnEl) {
        if (!inputEl || !btnEl) return;
        btnEl.addEventListener('click', (e) => {
            e.preventDefault();
            const icon = btnEl.querySelector('i');
            if (inputEl.type === 'password') {
                inputEl.type = 'text';
                if (icon) {
                    icon.classList.remove('bi-eye-fill');
                    icon.classList.add('bi-eye-slash-fill');
                }
            } else {
                inputEl.type = 'password';
                if (icon) {
                    icon.classList.remove('bi-eye-slash-fill');
                    icon.classList.add('bi-eye-fill');
                }
            }
        });
    }

    setupPasswordToggle(passwordInput, togglePasswordBtn);
    setupPasswordToggle(confirmPasswordInput, toggleConfirmPasswordBtn);

    // Clear all inline errors
    function clearErrors() {
        if (successAlert) successAlert.classList.add('d-none');
        if (errorAlert) errorAlert.classList.add('d-none');

        const fields = ['first_name', 'last_name', 'username', 'email', 'password', 'confirm_password'];
        fields.forEach(field => {
            const input = document.getElementById(field);
            const errDiv = document.getElementById(`error-${field}`);
            if (input) {
                input.classList.remove('is-invalid');
            }
            if (errDiv) {
                errDiv.textContent = '';
                errDiv.classList.remove('active');
            }
        });
    }

    // Set field error
    function setFieldError(fieldName, message) {
        const input = document.getElementById(fieldName);
        const errDiv = document.getElementById(`error-${fieldName}`);
        if (input) {
            input.classList.add('is-invalid');
        }
        if (errDiv) {
            errDiv.textContent = Array.isArray(message) ? message.join(' ') : message;
            errDiv.classList.add('active');
        }
    }

    // Client-side Validation
    function validateForm() {
        clearErrors();
        let isValid = true;

        const usernameVal = usernameInput ? usernameInput.value.trim() : '';
        const emailVal = emailInput ? emailInput.value.trim() : '';
        const passwordVal = passwordInput ? passwordInput.value : '';
        const confirmPasswordVal = confirmPasswordInput ? confirmPasswordInput.value : '';

        // Username validation
        if (!usernameVal) {
            setFieldError('username', 'Username is required.');
            isValid = false;
        } else if (usernameVal.length < 3) {
            setFieldError('username', 'Username must be at least 3 characters.');
            isValid = false;
        } else if (!/^[a-zA-Z0-9_@.-]+$/.test(usernameVal)) {
            setFieldError('username', 'Username may only contain letters, numbers, and @/./-/_ characters.');
            isValid = false;
        }

        // Email validation
        if (!emailVal) {
            setFieldError('email', 'Email address is required.');
            isValid = false;
        } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailVal)) {
            setFieldError('email', 'Please enter a valid email address.');
            isValid = false;
        }

        // Password validation
        if (!passwordVal) {
            setFieldError('password', 'Password is required.');
            isValid = false;
        } else if (passwordVal.length < 8) {
            setFieldError('password', 'Password must be at least 8 characters long.');
            isValid = false;
        }

        // Confirm Password validation
        if (!confirmPasswordVal) {
            setFieldError('confirm_password', 'Please confirm your password.');
            isValid = false;
        } else if (passwordVal !== confirmPasswordVal) {
            setFieldError('confirm_password', 'Passwords do not match.');
            isValid = false;
        }

        return isValid;
    }

    // Submit handler
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        // 1. Frontend Validation
        if (!validateForm()) {
            return;
        }

        // 2. Disable button & show spinner
        submitBtn.disabled = true;
        if (btnSpinner) btnSpinner.classList.remove('d-none');
        if (btnText) btnText.textContent = 'Creating Admin Account...';

        const payload = {
            first_name: firstNameInput ? firstNameInput.value.trim() : '',
            last_name: lastNameInput ? lastNameInput.value.trim() : '',
            username: usernameInput ? usernameInput.value.trim() : '',
            email: emailInput ? emailInput.value.trim() : '',
            password: passwordInput ? passwordInput.value : '',
            confirm_password: confirmPasswordInput ? confirmPasswordInput.value : ''
        };

        const csrfToken = getCsrfToken();

        try {
            // 3. Authenticated API Request to existing endpoint
            const response = await fetch('/api/admin/register/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || ''
                },
                credentials: 'same-origin',
                body: JSON.stringify(payload)
            });

            const data = await response.json();

            if (response.status === 201) {
                // 4. Success handling
                if (successAlert && successText) {
                    successText.textContent = data.message || 'Admin account created successfully.';
                    successAlert.classList.remove('d-none');
                }
                form.reset();
                if (passwordInput && togglePasswordBtn) {
                    passwordInput.type = 'password';
                    const icon = togglePasswordBtn.querySelector('i');
                    if (icon) icon.className = 'bi bi-eye-fill';
                }
                if (confirmPasswordInput && toggleConfirmPasswordBtn) {
                    confirmPasswordInput.type = 'password';
                    const icon = toggleConfirmPasswordBtn.querySelector('i');
                    if (icon) icon.className = 'bi bi-eye-fill';
                }
                window.scrollTo({ top: 0, behavior: 'smooth' });
            } else if (response.status === 400) {
                // 5. Backend Serializer Error handling
                if (typeof data === 'object') {
                    let hasMappedError = false;
                    for (const [key, val] of Object.entries(data)) {
                        if (['first_name', 'last_name', 'username', 'email', 'password', 'confirm_password'].includes(key)) {
                            setFieldError(key, val);
                            hasMappedError = true;
                        }
                    }
                    if (!hasMappedError && errorAlert && errorText) {
                        errorText.textContent = data.detail || data.non_field_errors || 'Validation error occurred.';
                        errorAlert.classList.remove('d-none');
                    }
                }
            } else if (response.status === 401 || response.status === 403) {
                if (errorAlert && errorText) {
                    errorText.textContent = data.detail || 'Permission denied. Only authorized Superusers can create Admin accounts.';
                    errorAlert.classList.remove('d-none');
                }
            } else {
                if (errorAlert && errorText) {
                    errorText.textContent = data.detail || 'An unexpected server error occurred. Please try again.';
                    errorAlert.classList.remove('d-none');
                }
            }
        } catch (err) {
            if (errorAlert && errorText) {
                errorText.textContent = 'Network error. Please check your internet connection and try again.';
                errorAlert.classList.remove('d-none');
            }
        } finally {
            // Re-enable button
            submitBtn.disabled = false;
            if (btnSpinner) btnSpinner.classList.add('d-none');
            if (btnText) btnText.textContent = 'Create Admin Account';
        }
    });
});
