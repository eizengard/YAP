/**
 * Common JavaScript utilities for the Language Learning App
 */

// Helper function to get CSRF token
function getCSRFToken() {
    const tokenElement = document.querySelector('meta[name="csrf-token"]');
    if (!tokenElement) {
        console.error('CSRF token meta tag not found');
        return null;
    }
    return tokenElement.getAttribute('content');
}

// Helper function for making API requests that include CSRF token
async function fetchWithCSRF(url, options = {}) {
    const csrfToken = getCSRFToken();
    
    // Default options
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        }
    };
    
    // Merge options
    const mergedOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...(options.headers || {})
        }
    };
    
    try {
        const response = await fetch(url, mergedOptions);
        
        if (!response.ok) {
            const errorText = await response.text();
            throw new Error(`API request failed: ${response.status} - ${errorText}`);
        }
        
        return response;
    } catch (error) {
        console.error('API request error:', error);
        throw error;
    }
}
