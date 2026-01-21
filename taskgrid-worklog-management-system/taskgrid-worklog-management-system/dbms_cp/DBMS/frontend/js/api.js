// TaskGrid API Handler
class TaskGridAPI {
    constructor() {
        this.baseURL = CONFIG.API_BASE_URL;
        this.token = localStorage.getItem(CONFIG.STORAGE_KEYS.TOKEN);
    }

    // Set authentication token
    setToken(token) {
        this.token = token;
        if (token) {
            localStorage.setItem(CONFIG.STORAGE_KEYS.TOKEN, token);
        } else {
            localStorage.removeItem(CONFIG.STORAGE_KEYS.TOKEN);
        }
    }

    // Get current user from storage
    getCurrentUser() {
        const userStr = localStorage.getItem(CONFIG.STORAGE_KEYS.USER);
        return userStr ? JSON.parse(userStr) : null;
    }

    // Set current user in storage
    setCurrentUser(user) {
        if (user) {
            localStorage.setItem(CONFIG.STORAGE_KEYS.USER, JSON.stringify(user));
        } else {
            localStorage.removeItem(CONFIG.STORAGE_KEYS.USER);
        }
    }

    // Generic API call method
    async apiCall(endpoint, method = 'GET', data = null) {
        const url = `${this.baseURL}${endpoint}`;
        const options = {
            method,
            headers: {
                'Content-Type': 'application/json',
            }
        };

        // Add authorization header if token exists
        if (this.token) {
            options.headers['Authorization'] = `Bearer ${this.token}`;
        }

        // Add body for POST/PUT requests
        if (data && (method === 'POST' || method === 'PUT')) {
            options.body = JSON.stringify(data);
        }

        try {
            const response = await fetch(url, options);
            const result = await response.json();

            if (!response.ok) {
                throw new Error(result.error || `HTTP error! status: ${response.status}`);
            }

            return result;
        } catch (error) {
            console.error('API call failed:', error);
            throw error;
        }
    }

    // Authentication Methods
    async login(username, password) {
        const response = await this.apiCall(CONFIG.ENDPOINTS.LOGIN, 'POST', {
            username,
            password
        });

        if (response.access_token) {
            this.setToken(response.access_token);
            this.setCurrentUser(response.user);
        }

        return response;
    }

    async register(userData) {
        return await this.apiCall(CONFIG.ENDPOINTS.REGISTER, 'POST', userData);
    }

    // Data Methods
    async getDashboard() {
        return await this.apiCall(CONFIG.ENDPOINTS.DASHBOARD);
    }

    async getProjects() {
        return await this.apiCall(CONFIG.ENDPOINTS.PROJECTS);
    }

    async getTasks() {
        return await this.apiCall(CONFIG.ENDPOINTS.TASKS);
    }

    // Utility Methods
    logout() {
        this.setToken(null);
        this.setCurrentUser(null);
        // Redirect to landing page
        window.location.reload();
    }

    isAuthenticated() {
        return !!this.token && !!this.getCurrentUser();
    }
}

// Create global API instance
if (typeof window !== 'undefined') {
    window.api = new TaskGridAPI();
}