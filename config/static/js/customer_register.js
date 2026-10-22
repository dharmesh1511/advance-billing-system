/**
 * Customer Registration Frontend Script
 * Advance Billing System with QR
 * Handles client-side validation, async registration via REST API,
 * dynamic error mapping, and submission state management.
 */

(function () {
    'use strict';

    // DOM Elements
    const form = document.getElementById('customer-registration-form');
    if (!form) return;

    const submitBtn = document.getElementById('btn-submit');
    const submitText = submitBtn ? submitBtn.querySelector('.btn-text') : null;
    const submitSpinner = submitBtn ? submitBtn.querySelector('.btn-spinner') : null;

    const globalErrorAlert = document.getElementById('global-error-alert');
    const globalErrorMessage = document.getElementById('global-error-message');
    const globalSuccessAlert = document.getElementById('global-success-alert');
    const globalSuccessMessage = document.getElementById('global-success-message');
    const btnRegisterAnother = document.getElementById('btn-register-another');

    // Field inputs
    const fields = {
        name: document.getElementById('id_name'),
        phone: document.getElementById('id_phone'),
        email: document.getElementById('id_email'),
        pincode: document.getElementById('id_pincode'),
        city: document.getElementById('id_city'),
        state: document.getElementById('id_state'),
        address: document.getElementById('id_address')
    };

    // Configuration
    const config = window.CUSTOMER_REGISTER_CONFIG || {
        apiEndpoint: '/api/distributor/customers/register/',
        customerListUrl: '/distributor/customers/',
        loginUrl: '/distributor/login/'
    };

    let isSubmitting = false;
    let redirectTimer = null;

    /**
     * Helper to get Cookie value by name (for CSRF token)
     */
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    /**
     * Clear all error messages and invalid states
     */
    function clearAllErrors() {
        if (globalErrorAlert) {
            globalErrorAlert.style.display = 'none';
            if (globalErrorMessage) globalErrorMessage.textContent = '';
        }

        Object.keys(fields).forEach(fieldName => {
            const input = fields[fieldName];
            if (input) {
                input.classList.remove('is-invalid');
            }
            const errorContainer = document.getElementById(`${fieldName}-error`);
            if (errorContainer) {
                errorContainer.textContent = '';
            }
        });
    }

    /**
     * Set field error
     */
    function setFieldError(fieldName, message) {
        const input = fields[fieldName];
        if (input) {
            input.classList.add('is-invalid');
        }
        const errorContainer = document.getElementById(`${fieldName}-error`);
        if (errorContainer) {
            errorContainer.textContent = message;
        }
    }

    /**
     * Clear specific field error
     */
    function clearFieldError(fieldName) {
        const input = fields[fieldName];
        if (input) {
            input.classList.remove('is-invalid');
        }
        const errorContainer = document.getElementById(`${fieldName}-error`);
        if (errorContainer) {
            errorContainer.textContent = '';
        }
    }

    /**
     * Show global error message
     */
    function showGlobalError(message) {
        if (globalErrorAlert && globalErrorMessage) {
            globalErrorMessage.textContent = message;
            globalErrorAlert.style.display = 'flex';
            globalErrorAlert.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    }

    /**
     * Client-side validation logic
     */
    function validateForm(data) {
        let isValid = true;
        let firstInvalidField = null;

        // Name: required, min 2 chars, non-digit-only
        const nameVal = (data.name || '').trim();
        if (!nameVal) {
            setFieldError('name', 'Customer name is required.');
            isValid = false;
            if (!firstInvalidField) firstInvalidField = fields.name;
        } else if (nameVal.length < 2) {
            setFieldError('name', 'Customer name must be at least 2 characters.');
            isValid = false;
            if (!firstInvalidField) firstInvalidField = fields.name;
        } else if (/^\d+$/.test(nameVal)) {
            setFieldError('name', 'Customer name cannot consist of numbers only.');
            isValid = false;
            if (!firstInvalidField) firstInvalidField = fields.name;
        }

        // Phone: required, 10 digits starting with 6-9
        const phoneVal = (data.phone || '').trim();
        if (!phoneVal) {
            setFieldError('phone', 'Phone number is required.');
            isValid = false;
            if (!firstInvalidField) firstInvalidField = fields.phone;
        } else {
            const cleanPhone = phoneVal.replace(/[\s\-\+]/g, '');
            const phoneRegex = /^[6-9]\d{9}$/;
            if (!phoneRegex.test(cleanPhone)) {
                setFieldError('phone', 'Enter a valid 10-digit Indian mobile number starting with 6, 7, 8, or 9.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = fields.phone;
            }
        }

        // Email: optional, validate if present
        const emailVal = (data.email || '').trim();
        if (emailVal) {
            const emailRegex = /^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$/;
            if (!emailRegex.test(emailVal) || emailVal.length > 254) {
                setFieldError('email', 'Enter a valid email address.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = fields.email;
            }
        }

        // PIN Code: optional, 6 digits
        const pinVal = (data.pincode || '').trim();
        if (pinVal) {
            if (!/^\d{6}$/.test(pinVal)) {
                setFieldError('pincode', 'PIN Code must be exactly 6 digits.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = fields.pincode;
            }
        }

        // City: optional, max 100, no numbers
        const cityVal = (data.city || '').trim();
        if (cityVal) {
            if (/\d/.test(cityVal)) {
                setFieldError('city', 'City cannot contain numbers.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = fields.city;
            } else if (cityVal.length > 100) {
                setFieldError('city', 'City cannot exceed 100 characters.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = fields.city;
            }
        }

        // State: optional, max 100, no numbers
        const stateVal = (data.state || '').trim();
        if (stateVal) {
            if (/\d/.test(stateVal)) {
                setFieldError('state', 'State cannot contain numbers.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = fields.state;
            } else if (stateVal.length > 100) {
                setFieldError('state', 'State cannot exceed 100 characters.');
                isValid = false;
                if (!firstInvalidField) firstInvalidField = fields.state;
            }
        }

        if (firstInvalidField) {
            firstInvalidField.focus();
        }

        return isValid;
    }

    /**
     * Toggle button loading state
     */
    function setLoading(loading) {
        isSubmitting = loading;
        if (submitBtn) {
            submitBtn.disabled = loading;
        }
        if (submitSpinner) {
            submitSpinner.style.display = loading ? 'inline-block' : 'none';
        }
        if (submitText) {
            submitText.textContent = loading ? 'Registering...' : 'Register Customer';
        }
    }

    // Attach live input clearing
    Object.keys(fields).forEach(key => {
        const input = fields[key];
        if (input) {
            input.addEventListener('input', () => {
                clearFieldError(key);
                if (globalErrorAlert && globalErrorAlert.style.display !== 'none') {
                    globalErrorAlert.style.display = 'none';
                }
            });
        }
    });

    /**
     * Submit Handler
     */
    form.addEventListener('submit', async function (e) {
        e.preventDefault();

        if (isSubmitting) return;

        // Clear existing states
        clearAllErrors();
        if (globalSuccessAlert) {
            globalSuccessAlert.style.display = 'none';
        }

        // Collect and trim values
        const payload = {
            name: fields.name ? fields.name.value.trim() : '',
            phone: fields.phone ? fields.phone.value.trim() : '',
            email: fields.email ? fields.email.value.trim() : '',
            address: fields.address ? fields.address.value.trim() : '',
            city: fields.city ? fields.city.value.trim() : '',
            state: fields.state ? fields.state.value.trim() : '',
            pincode: fields.pincode ? fields.pincode.value.trim() : ''
        };

        // Client validation
        if (!validateForm(payload)) {
            return;
        }

        // Clean payload for API (empty strings to empty string or null)
        const apiPayload = {
            name: payload.name,
            phone: payload.phone
        };
        if (payload.email) apiPayload.email = payload.email;
        if (payload.address) apiPayload.address = payload.address;
        if (payload.city) apiPayload.city = payload.city;
        if (payload.state) apiPayload.state = payload.state;
        if (payload.pincode) apiPayload.pincode = payload.pincode;

        // Prepare headers
        const csrfToken = getCookie('csrftoken') || (form.querySelector('[name=csrfmiddlewaretoken]') ? form.querySelector('[name=csrfmiddlewaretoken]').value : '');
        const headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        };

        if (csrfToken) {
            headers['X-CSRFToken'] = csrfToken;
        }

        // Support JWT Bearer token if stored in localStorage / sessionStorage
        const jwtToken = localStorage.getItem('access_token') || sessionStorage.getItem('access_token');
        if (jwtToken) {
            headers['Authorization'] = `Bearer ${jwtToken}`;
        }

        setLoading(true);

        try {
            const response = await fetch(config.apiEndpoint, {
                method: 'POST',
                headers: headers,
                credentials: 'same-origin',
                body: JSON.stringify(apiPayload)
            });

            const responseData = await response.json().catch(() => ({}));

            if (response.status === 201) {
                // SUCCESS
                const customerData = responseData.customer || responseData;
                const customerName = customerData.name || payload.name;

                if (globalSuccessAlert && globalSuccessMessage) {
                    globalSuccessMessage.innerHTML = `Customer <strong>${escapeHtml(customerName)}</strong> registered successfully!`;
                    globalSuccessAlert.style.display = 'flex';
                    globalSuccessAlert.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
                }

                // Hide form or disable fields
                form.style.display = 'none';

                // Automatically redirect to customer list after 3 seconds
                if (config.customerListUrl) {
                    redirectTimer = setTimeout(() => {
                        window.location.href = config.customerListUrl;
                    }, 2800);
                }

            } else if (response.status === 400) {
                // BACKEND VALIDATION ERRORS
                let hasFieldErrors = false;
                let firstBadField = null;

                if (typeof responseData === 'object' && responseData !== null) {
                    Object.keys(responseData).forEach(field => {
                        const err = responseData[field];
                        const errText = Array.isArray(err) ? err.join(' ') : String(err);

                        if (fields[field]) {
                            setFieldError(field, errText);
                            hasFieldErrors = true;
                            if (!firstBadField) firstBadField = fields[field];
                        } else if (field === 'non_field_errors' || field === 'detail') {
                            showGlobalError(errText);
                        } else {
                            showGlobalError(`${field}: ${errText}`);
                        }
                    });
                }

                if (firstBadField) {
                    firstBadField.focus();
                } else if (!hasFieldErrors) {
                    showGlobalError('Validation failed. Please verify the entered information.');
                }

            } else if (response.status === 401 || response.status === 403) {
                // UNAUTHORIZED / FORBIDDEN
                const msg = responseData.detail || 'Your session has expired or you do not have distributor permissions.';
                showGlobalError(msg + ' Please login again.');
                setTimeout(() => {
                    if (config.loginUrl) {
                        window.location.href = config.loginUrl;
                    }
                }, 2500);

            } else {
                // OTHER ERRORS
                const msg = responseData.detail || responseData.error || 'Unable to register customer right now. Please try again later.';
                showGlobalError(msg);
            }

        } catch (error) {
            console.error('Registration network error:', error);
            showGlobalError('Network error: Unable to connect to server. Please check your internet connection and try again.');
        } finally {
            setLoading(false);
        }
    });

    /**
     * "Register Another Customer" button handler
     */
    if (btnRegisterAnother) {
        btnRegisterAnother.addEventListener('click', function () {
            if (redirectTimer) {
                clearTimeout(redirectTimer);
                redirectTimer = null;
            }

            // Reset form
            form.reset();
            clearAllErrors();

            // Hide success alert, show form
            if (globalSuccessAlert) {
                globalSuccessAlert.style.display = 'none';
            }
            form.style.display = 'block';

            // Focus on name input
            if (fields.name) {
                fields.name.focus();
            }
        });
    }

    /**
     * HTML entity escaping helper to prevent XSS in displayed messages
     */
    function escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, function (m) { return map[m]; });
    }

})();
