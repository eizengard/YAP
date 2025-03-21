document.addEventListener('DOMContentLoaded', () => {
    const vocabularyExercise = document.getElementById('vocabulary-exercise');
    const playWordAudioBtn = document.getElementById('play-word-audio');
    const playSentenceAudioBtn = document.getElementById('play-sentence-audio');
    const showHintBtn = document.getElementById('show-hint');
    const prevWordBtn = document.getElementById('prev-word');
    const nextWordBtn = document.getElementById('next-word');
    
    // State variables
    let currentWord = null;
    let currentMode = 'flashcards'; // Default to flashcards
    let audioPlayer = null;
    let currentCategory = null;
    let isUpdatingUI = false; // Flag to prevent race conditions

    // Initialize with the current category from URL
    const urlParams = new URLSearchParams(window.location.search);
    currentCategory = urlParams.get('category');
    
    // Check for values set in the template
    if (window.currentWord) {
        currentWord = window.currentWord;
        console.log('Loaded currentWord from window', currentWord);
    }
    
    if (window.currentMode) {
        currentMode = window.currentMode;
        console.log('Loaded currentMode from window', currentMode);
    }
    
    if (window.currentCategory) {
        currentCategory = window.currentCategory;
        console.log('Loaded currentCategory from window', currentCategory);
    }
    
    // Expose functions and variables to the global scope
    window.vocabularyJS = {
        loadExercise: (mode, category) => loadExercise(mode, category),
        setCurrentWord: (word) => { currentWord = word; },
        setCurrentMode: (mode) => { currentMode = mode; },
        setCurrentCategory: (category) => { currentCategory = category; },
        // Make sure the template doesn't override our display
        displayInitialWord: (word) => {
            // Only do this if we haven't already displayed a word
            if (!currentWord) {
                currentWord = word;
                displayExercise(currentMode, word);
            }
        }
    };
    
    // Start practice session
    document.querySelectorAll('.start-practice').forEach(button => {
        button.addEventListener('click', async () => {
            const mode = button.dataset.mode;
            currentMode = mode;
            await loadExercise(mode, currentCategory);
        });
    });

    async function loadExercise(mode, category) {
        // Prevent multiple rapid calls
        if (isUpdatingUI) {
            console.log('Skipping update, already in progress');
            return null;
        }
        
        isUpdatingUI = true;
        
        try {
            console.log('Loading exercise', {mode, category});
            
            // Show loading spinner while fetching new word
            vocabularyExercise.innerHTML = `
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Loading...</span>
                </div>
            `;
            
            const url = category 
                ? `/api/vocabulary/exercise?mode=${mode}&category=${encodeURIComponent(category)}`
                : `/api/vocabulary/exercise?mode=${mode}`;
                
            const response = await fetch(url);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to load exercise');
            }

            // Clear any existing timeouts that might interfere
            if (window.vocabUpdateTimeout) {
                clearTimeout(window.vocabUpdateTimeout);
            }

            // Update current word and global variables
            currentWord = data;
            window.currentWord = data;
            window.currentMode = mode;
            window.currentCategory = category;
            
            console.log('Exercise loaded successfully', data);
            console.log('Displaying new word:', data.word);
            
            // Display the new exercise
            displayExercise(mode, data);
            
            // Debug - check what's in the DOM after we've updated it
            window.vocabUpdateTimeout = setTimeout(() => {
                console.log('Current DOM content:', vocabularyExercise.innerHTML);
                console.log('Current word element:', vocabularyExercise.querySelector('.word')?.textContent);
                // Release the update lock
                isUpdatingUI = false;
            }, 200);
            
            // Enable audio buttons
            playWordAudioBtn.disabled = false;
            playSentenceAudioBtn.disabled = false;
            
            return data; // Return the data for chaining
        } catch (error) {
            console.error('Failed to load exercise:', error);
            vocabularyExercise.innerHTML = '<div class="alert alert-danger">Failed to load exercise</div>';
            isUpdatingUI = false;
            return null;
        }
    }

    function displayExercise(mode, data) {
        switch (mode) {
            case 'flashcards':
                displayFlashcard(data);
                break;
            case 'multiple-choice':
                displayMultipleChoice(data);
                break;
            case 'typing':
                displayTypingExercise(data);
                break;
        }
    }

    function displayFlashcard(data) {
        console.log('Displaying flashcard', data);
        
        // Completely replace the content
        vocabularyExercise.innerHTML = '';
        
        // Create a unique ID for this flashcard to avoid DOM conflicts
        const cardId = `flashcard-${Date.now()}`;
        
        // Create card element
        const card = document.createElement('div');
        card.className = 'card flashcard';
        card.id = cardId;
        
        // Create card body
        const cardBody = document.createElement('div');
        cardBody.className = 'card-body';
        
        // Add word
        const wordElem = document.createElement('h3');
        wordElem.className = 'word mb-4';
        wordElem.textContent = data.word;
        wordElem.id = `${cardId}-word`;
        cardBody.appendChild(wordElem);
        
        // Add translation container (hidden initially)
        const translationDiv = document.createElement('div');
        translationDiv.className = 'translation';
        translationDiv.id = `${cardId}-translation`;
        translationDiv.style.display = 'none';
        
        // Add translation
        const translationElem = document.createElement('h4');
        translationElem.textContent = data.translation;
        translationDiv.appendChild(translationElem);
        
        // Add example sentence
        const exampleElem = document.createElement('p');
        exampleElem.className = 'example-sentence text-muted';
        exampleElem.textContent = data.example_sentence;
        translationDiv.appendChild(exampleElem);
        
        // Add translation to card body
        cardBody.appendChild(translationDiv);
        
        // Add card body to card
        card.appendChild(cardBody);
        
        // Add card to exercise container
        vocabularyExercise.appendChild(card);
        
        // Add show translation button
        const showButton = document.createElement('button');
        showButton.className = 'btn btn-lg btn-primary mt-3';
        showButton.textContent = 'Show Translation';
        showButton.id = `${cardId}-show-btn`;
        
        // Use a more reliable way to show the translation
        showButton.addEventListener('click', function() {
            // Find the translation by ID to ensure we're targeting the right element
            const translationToShow = document.getElementById(`${cardId}-translation`);
            if (translationToShow) {
                translationToShow.style.display = 'block';
                // Disable the button after showing to prevent multiple clicks
                this.disabled = true;
            } else {
                console.error('Translation element not found by ID');
            }
        });
        
        vocabularyExercise.appendChild(showButton);
        
        // Log the created DOM for debugging
        console.log('Created flashcard DOM:', {
            cardId,
            wordElem: document.getElementById(`${cardId}-word`),
            translationDiv: document.getElementById(`${cardId}-translation`),
            showButton: document.getElementById(`${cardId}-show-btn`)
        });
    }

    function displayMultipleChoice(data) {
        const options = shuffleArray([data.translation, ...(data.distractors || [])]);
        vocabularyExercise.innerHTML = `
            <h3 class="mb-4">${data.word}</h3>
            <div class="options-container">
                ${options.map((option, index) => `
                    <button class="btn btn-outline-primary btn-lg mb-2 w-100" onclick="checkAnswer(this, '${data.translation}')">
                        ${option}
                    </button>
                `).join('')}
            </div>
        `;
    }

    function displayTypingExercise(data) {
        console.log('Displaying typing exercise', data);
        
        // Create a unique ID for this input to avoid DOM conflicts
        const inputId = `typing-input-${Date.now()}`;
        const formId = `typing-form-${Date.now()}`;
        
        vocabularyExercise.innerHTML = `
            <div class="typing-exercise">
                <h3 class="word mb-4">${data.word}</h3>
                <p class="text-muted mb-3">Type the translation in ${data.language === 'en' ? 'English' : data.language === 'es' ? 'Spanish' : data.language === 'fr' ? 'French' : data.language === 'de' ? 'German' : data.language === 'it' ? 'Italian' : data.language}</p>
                <form id="${formId}" class="mb-3" autocomplete="off">
                    <div class="form-group">
                        <input type="text" 
                               id="${inputId}" 
                               class="form-control form-control-lg mb-3" 
                               placeholder="Type your answer here" 
                               autocomplete="off"
                               autocorrect="off"
                               autocapitalize="off"
                               spellcheck="false">
                        <button type="submit" class="btn btn-primary btn-lg w-100">
                            Check Answer
                        </button>
                    </div>
                </form>
                <div id="feedback-area" class="mt-3"></div>
            </div>
        `;
        
        // Set focus on the input field
        setTimeout(() => {
            const inputField = document.getElementById(inputId);
            if (inputField) {
                inputField.focus();
            }
        }, 100);
        
        // Add form submit event listener
        const form = document.getElementById(formId);
        if (form) {
            form.addEventListener('submit', function(e) {
                e.preventDefault();
                const input = document.getElementById(inputId);
                const userAnswer = input.value.trim().toLowerCase();
                const correctAnswer = data.translation.toLowerCase();
                const feedbackArea = document.getElementById('feedback-area');
                
                input.disabled = true;
                
                // Find the submit button and disable it
                const submitButton = form.querySelector('button[type="submit"]');
                if (submitButton) {
                    submitButton.disabled = true;
                }
                
                // Check if answer is correct
                let isCorrect = false;
                
                // Exact match
                if (userAnswer === correctAnswer) {
                    isCorrect = true;
                }
                // Allow minor typos (remove spaces, accents, punctuation)
                else {
                    const normalizedUserAnswer = userAnswer.replace(/[\s.,;:!?'"()-]/g, '').normalize("NFD").replace(/[\u0300-\u036f]/g, "");
                    const normalizedCorrectAnswer = correctAnswer.replace(/[\s.,;:!?'"()-]/g, '').normalize("NFD").replace(/[\u0300-\u036f]/g, "");
                    
                    if (normalizedUserAnswer === normalizedCorrectAnswer) {
                        isCorrect = true;
                    }
                }
                
                if (isCorrect) {
                    input.classList.add('is-valid');
                    feedbackArea.innerHTML = `
                        <div class="alert alert-success">
                            <i class="bi bi-check-circle-fill me-2"></i>
                            Correct! Well done.
                        </div>
                    `;
                    saveProgress(true);
                } else {
                    input.classList.add('is-invalid');
                    feedbackArea.innerHTML = `
                        <div class="alert alert-danger">
                            <i class="bi bi-x-circle-fill me-2"></i>
                            Not quite. The correct answer is: <strong>${data.translation}</strong>
                        </div>
                    `;
                    saveProgress(false);
                }
                
                // Wait a moment, then load the next word
                setTimeout(() => loadNextWord(), 2000);
            });
        }
    }

    // Audio playback for word
    playWordAudioBtn.addEventListener('click', async () => {
        console.log('Play word audio button clicked', currentWord);
        if (!currentWord) {
            console.error('No current word available');
            return;
        }
        await playAudio(currentWord.word, currentWord.language);
    });

    // Audio playback for example sentence
    playSentenceAudioBtn.addEventListener('click', async () => {
        console.log('Play sentence audio button clicked', currentWord);
        if (!currentWord || !currentWord.example_sentence) {
            console.error('No example sentence available');
            return;
        }
        await playAudio(currentWord.example_sentence, currentWord.language);
    });

    // Common audio playback function
    async function playAudio(text, language) {
        try {
            console.log('Attempting to play audio for:', text, language);
            
            // Get CSRF token from meta tag
            const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
            if (!csrfToken) {
                console.error('CSRF token not found');
            }
            
            // Show loading state on button
            const btn = text === currentWord.word ? playWordAudioBtn : playSentenceAudioBtn;
            const originalText = btn.innerHTML;
            btn.disabled = true;
            btn.innerHTML = '<i class="bi bi-hourglass-split"></i> Loading...';
            
            console.log('Sending request to text-to-speech API...');
            const response = await fetch('/api/text-to-speech', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken || ''
                },
                body: JSON.stringify({
                    text: text,
                    lang: language,
                    speed: 0.8,         // Slightly slower for better comprehension
                    model: 'tts-1-hd'   // Higher quality audio
                }),
            });

            console.log('API response status:', response.status);
            const data = await response.json();
            console.log('API response data:', data);
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate audio');
            }

            console.log(`Playing audio for "${text.substring(0, 30)}..." (${language}) with voice "${data.voice}"`);

            // Reset button state
            btn.disabled = false;
            btn.innerHTML = originalText;

            if (audioPlayer) {
                audioPlayer.pause();
                audioPlayer = null;
            }

            audioPlayer = new Audio(data.audio_url);
            await audioPlayer.play();
            console.log('Audio playback started');
        } catch (error) {
            console.error('Audio playback failed:', error);
            
            // Reset button state
            const btn = text === currentWord.word ? playWordAudioBtn : playSentenceAudioBtn;
            btn.disabled = false;
            btn.innerHTML = text === currentWord.word ? 
                '<i class="bi bi-volume-up"></i> Word' : 
                '<i class="bi bi-volume-up-fill"></i> Sentence';
        }
    }

    // Create a dedicated function for loading the next word
    async function loadNextWord() {
        // Clear the exercise area immediately and show loading
        vocabularyExercise.innerHTML = `
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading next word...</span>
            </div>
        `;
        
        // Clear any existing timeouts
        if (window.vocabUpdateTimeout) {
            clearTimeout(window.vocabUpdateTimeout);
        }
        
        // Implement fetch with retry and fallback
        let retryCount = 0;
        const maxRetries = 3;
        
        async function fetchWithRetry() {
            try {
                const mode = currentMode || 'flashcards';
                // Generate a truly unique timestamp to prevent any cache issues
                const timestamp = Date.now() + Math.floor(Math.random() * 1000);
                const url = currentCategory 
                    ? `/api/vocabulary/exercise?mode=${mode}&category=${encodeURIComponent(currentCategory)}&timestamp=${timestamp}&skip_cache=true&random=${Math.random()}`
                    : `/api/vocabulary/exercise?mode=${mode}&timestamp=${timestamp}&skip_cache=true&random=${Math.random()}`;
                
                console.log(`Fetching new word from: ${url} (attempt ${retryCount + 1})`);
                const response = await fetch(url, {
                    method: 'GET',
                    cache: 'no-store', // Prevent caching
                    headers: {
                        'Pragma': 'no-cache',
                        'Cache-Control': 'no-cache, no-store, must-revalidate',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    credentials: 'same-origin'
                });
                
                // First try to parse JSON response
                let data;
                let errorText = '';
                
                try {
                    // Try to get the response as JSON
                    const contentType = response.headers.get('content-type');
                    if (contentType && contentType.indexOf('application/json') !== -1) {
                        data = await response.json();
                    } else {
                        // If not JSON, get as text
                        errorText = await response.text();
                        console.error('Non-JSON response:', errorText);
                        throw new Error('Unexpected response format');
                    }
                } catch (parseError) {
                    console.error('Error parsing response:', parseError);
                    throw new Error(`Response parse error: ${errorText || parseError.message}`);
                }
                
                if (!response.ok) {
                    throw new Error(`Server error: ${response.status} - ${JSON.stringify(data)}`);
                }
                
                console.log('New word received:', data);
                
                // Update state
                currentWord = data;
                window.currentWord = data;
                
                // Display the new word immediately using the correct display function based on mode
                displayExercise(mode, data);
                
                // Enable audio buttons
                playWordAudioBtn.disabled = false;
                playSentenceAudioBtn.disabled = false;
                
                return true; // Success
            } catch (error) {
                console.error(`Error fetching next word (attempt ${retryCount + 1}):`, error);
                
                if (retryCount < maxRetries) {
                    retryCount++;
                    console.log(`Retrying... (${retryCount}/${maxRetries})`);
                    await new Promise(resolve => setTimeout(resolve, 500)); // Wait before retry
                    return fetchWithRetry();
                } else {
                    // All retries failed - try a fallback approach
                    console.log('All retries failed, attempting fallback method');
                    
                    // Try a simplified API call without parameters to get any word
                    try {
                        const fallbackUrl = `/api/vocabulary/exercise?timestamp=${Date.now()}&fallback=true`;
                        const fallbackResponse = await fetch(fallbackUrl, { 
                            cache: 'no-store',
                            credentials: 'same-origin'
                        });
                        
                        if (fallbackResponse.ok) {
                            const fallbackData = await fallbackResponse.json();
                            currentWord = fallbackData;
                            window.currentWord = fallbackData;
                            displayExercise(currentMode || 'flashcards', fallbackData);
                            console.log('Fallback successful');
                            return true;
                        }
                    } catch (fallbackError) {
                        console.error('Fallback attempt also failed:', fallbackError);
                    }
                    
                    // If all fails, show error message with reload button
                    vocabularyExercise.innerHTML = `
                        <div class="alert alert-danger">
                            <h5><i class="bi bi-exclamation-circle me-2"></i>Unable to load vocabulary</h5>
                            <p>We're having trouble connecting to the server. Please try again later.</p>
                            <div class="mt-3">
                                <button class="btn btn-outline-primary me-2" onclick="location.reload()">
                                    <i class="bi bi-arrow-clockwise me-1"></i> Reload Page
                                </button>
                                <button class="btn btn-outline-secondary" onclick="window.vocabularyJS.loadExercise('flashcards')">
                                    <i class="bi bi-arrow-repeat me-1"></i> Try Different Word
                                </button>
                            </div>
                        </div>
                    `;
                    return false;
                }
            }
        }
        
        return await fetchWithRetry();
    }

    // Navigation - load prev/next words
    nextWordBtn.addEventListener('click', async () => {
        console.log('Next button clicked', {currentMode, currentCategory});
        await loadNextWord();
    });
    
    // Previous button also uses the same function for consistency
    prevWordBtn.addEventListener('click', async () => {
        console.log('Previous button clicked', {currentMode, currentCategory});
        await loadNextWord();
    });

    // Show hint (for now it's just show translation)
    showHintBtn.addEventListener('click', () => {
        console.log('Show hint button clicked', currentWord);
        if (currentWord) {
            // Try to find the translation by searching for a flashcard translation element
            const translationElems = vocabularyExercise.querySelectorAll('[id$="-translation"]');
            if (translationElems.length > 0) {
                const translationElem = translationElems[0]; // Use the first one found
                translationElem.style.display = 'block';
                console.log('Translation shown by ID', translationElem.id);
                
                // Also disable any show buttons
                const showBtns = vocabularyExercise.querySelectorAll('[id$="-show-btn"]');
                showBtns.forEach(btn => {
                    btn.disabled = true;
                });
            } else {
                // Fall back to legacy approach
                const translationElem = vocabularyExercise.querySelector('.translation');
                if (translationElem) {
                    translationElem.style.display = 'block';
                    console.log('Translation shown by class');
                } else {
                    console.error('Translation element not found');
                }
            }
        } else {
            console.error('No current word available for hint');
        }
    });

    // Utility functions
    function shuffleArray(array) {
        const newArray = [...array]; // Create a copy to avoid mutating the original
        for (let i = newArray.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [newArray[i], newArray[j]] = [newArray[j], newArray[i]];
        }
        return newArray;
    }

    // Checking answers
    window.checkAnswer = function(button, correctAnswer) {
        const buttons = button.parentElement.querySelectorAll('button');
        buttons.forEach(btn => btn.disabled = true);
        
        if (button.textContent.trim() === correctAnswer) {
            button.classList.remove('btn-outline-primary');
            button.classList.add('btn-success');
            saveProgress(true);
        } else {
            button.classList.remove('btn-outline-primary');
            button.classList.add('btn-danger');
            buttons.forEach(btn => {
                if (btn.textContent.trim() === correctAnswer) {
                    btn.classList.remove('btn-outline-primary');
                    btn.classList.add('btn-success');
                }
            });
            saveProgress(false);
        }

        // Wait a moment, then load the next word
        setTimeout(() => loadNextWord(), 1200);
    };

    async function saveProgress(isCorrect) {
        try {
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            await fetch('/api/vocabulary/progress', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    vocabulary_id: currentWord.id,
                    correct: isCorrect
                }),
            });
        } catch (error) {
            console.error('Failed to save progress:', error);
        }
    }
});
