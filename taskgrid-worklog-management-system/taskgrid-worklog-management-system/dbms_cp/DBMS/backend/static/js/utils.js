// TaskGrid Utility Functions
const Utils = {
    // Show toast notification
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed; top: 20px; right: 20px; z-index: 10000;
            background: ${type === 'success' ? '#2ad39a' : type === 'error' ? '#ff5d6c' : type === 'warn' ? '#ffb020' : '#06d7ff'};
            color: white; padding: 12px 20px; border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15); transform: translateX(100%);
            transition: transform 0.3s ease; max-width: 400px; font-family: Arial, sans-serif;
        `;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => toast.style.transform = 'translateX(0)', 100);
        setTimeout(() => {
            toast.style.transform = 'translateX(100%)';
            setTimeout(() => toast.remove(), 300);
        }, CONFIG.UI.TOAST_DURATION);
    },

    // Validate email format
    isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    },

    // Set loading state for button
    setLoading(button, isLoading) {
        if (isLoading) {
            button.disabled = true;
            button.dataset.originalText = button.textContent;
            button.textContent = 'Loading...';
        } else {
            button.disabled = false;
            button.textContent = button.dataset.originalText || button.textContent;
        }
    },

    // Handle API errors
    handleApiError(error, context = '') {
        console.error('API Error:', error);
        let message = 'An error occurred';
        
        if (error.message) {
            message = error.message;
        } else if (typeof error === 'string') {
            message = error;
        }
        
        if (context) {
            message += ` ${context}`;
        }
        
        this.showToast(message, 'error');
    },

    // Format date
    formatDate(dateString) {
        if (!dateString) return 'No date';
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', { 
            year: 'numeric', 
            month: 'short', 
            day: 'numeric' 
        });
    },

    // Debounce function
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    },

    // Local storage helpers
    storage: {
        set(key, value) {
            try {
                localStorage.setItem(CONFIG.STORAGE_PREFIX + key, JSON.stringify(value));
                return true;
            } catch (error) {
                console.error('Storage set error:', error);
                return false;
            }
        },

        get(key) {
            try {
                const item = localStorage.getItem(CONFIG.STORAGE_PREFIX + key);
                return item ? JSON.parse(item) : null;
            } catch (error) {
                console.error('Storage get error:', error);
                return null;
            }
        },

        remove(key) {
            try {
                localStorage.removeItem(CONFIG.STORAGE_PREFIX + key);
                return true;
            } catch (error) {
                console.error('Storage remove error:', error);
                return false;
            }
        },

        clear() {
            try {
                Object.keys(localStorage).forEach(key => {
                    if (key.startsWith(CONFIG.STORAGE_PREFIX)) {
                        localStorage.removeItem(key);
                    }
                });
                return true;
            } catch (error) {
                console.error('Storage clear error:', error);
                return false;
            }
        }
    }
};

// Make Utils globally available
window.Utils = Utils;