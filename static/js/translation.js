class TranslationManager {
    constructor() {
        this.cache = new Map();
        this.initializeTranslatables();
    }

    initializeTranslatables() {
        // Find all elements with the 'translatable' class
        const translatables = document.querySelectorAll('.translatable');
        
        translatables.forEach(element => {
            this.setupTranslatable(element);
        });
    }

    setupTranslatable(element) {
        // Create tooltip element
        const tooltip = document.createElement('div');
        tooltip.className = 'translation-tooltip';
        tooltip.textContent = 'Loading...';
        element.appendChild(tooltip);

        // Add hover event listeners
        element.addEventListener('mouseenter', async () => {
            const text = element.getAttribute('data-text') || element.textContent.trim();
            const sourceLang = element.getAttribute('data-source-lang');
            const targetLang = element.getAttribute('data-target-lang');

            // Check cache first
            const cacheKey = `${text}-${sourceLang}-${targetLang}`;
            if (this.cache.has(cacheKey)) {
                tooltip.textContent = this.cache.get(cacheKey);
                return;
            }

            try {
                const translation = await this.getTranslation(text, sourceLang, targetLang);
                tooltip.textContent = translation;
                this.cache.set(cacheKey, translation);
            } catch (error) {
                console.error('Translation error:', error);
                tooltip.textContent = 'Translation failed';
            }
        });
    }

    async getTranslation(text, sourceLang, targetLang) {
        try {
            // Get CSRF token from meta tag
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
            
            const response = await fetch('/api/translate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || ''
                },
                body: JSON.stringify({
                    text,
                    source_lang: sourceLang,
                    target_lang: targetLang
                })
            });

            if (!response.ok) {
                throw new Error('Translation request failed');
            }

            const data = await response.json();
            return data.translation;
        } catch (error) {
            console.error('API error:', error);
            throw error;
        }
    }

    // Method to dynamically add translatable elements
    addTranslatable(element) {
        this.setupTranslatable(element);
    }
}

// Initialize translation manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.translationManager = new TranslationManager();
});
