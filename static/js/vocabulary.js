document.addEventListener('DOMContentLoaded', () => {
    const vocabularyExercise = document.getElementById('vocabulary-exercise');
    const playAudioBtn = document.getElementById('play-audio');
    const showHintBtn = document.getElementById('show-hint');
    const prevWordBtn = document.getElementById('prev-word');
    const nextWordBtn = document.getElementById('next-word');
    
    let currentWord = null;
    let currentMode = null;
    let audioPlayer = null;

    // Start practice session
    document.querySelectorAll('.start-practice').forEach(button => {
        button.addEventListener('click', async () => {
            const mode = button.dataset.mode;
            currentMode = mode;
            await loadExercise(mode);
        });
    });

    async function loadExercise(mode) {
        try {
            const response = await fetch(`/api/vocabulary/exercise?mode=${mode}`);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to load exercise');
            }

            currentWord = data;
            displayExercise(mode, data);
        } catch (error) {
            console.error('Failed to load exercise:', error);
            vocabularyExercise.innerHTML = '<div class="alert alert-danger">Failed to load exercise</div>';
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
        vocabularyExercise.innerHTML = `
            <div class="card flashcard">
                <div class="card-body">
                    <h3 class="word mb-4">${data.word}</h3>
                    <div class="translation" style="display: none;">
                        <h4>${data.translation}</h4>
                        <p class="example-sentence text-muted">${data.example_sentence}</p>
                    </div>
                </div>
            </div>
            <button class="btn btn-lg btn-primary mt-3" onclick="this.previousElementSibling.querySelector('.translation').style.display='block'">
                Show Translation
            </button>
        `;
    }

    function displayMultipleChoice(data) {
        const options = shuffleArray([data.translation, ...data.distractors]);
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
        vocabularyExercise.innerHTML = `
            <h3 class="mb-4">${data.word}</h3>
            <div class="form-group">
                <input type="text" class="form-control form-control-lg mb-3" placeholder="Type the translation">
                <button class="btn btn-primary btn-lg" onclick="checkTypedAnswer(this)">Check Answer</button>
            </div>
        `;
    }

    // Audio playback
    playAudioBtn.addEventListener('click', async () => {
        if (!currentWord) return;

        try {
            // Get CSRF token from meta tag
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            
            const response = await fetch('/api/text-to-speech', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    text: currentWord.word,
                    lang: currentWord.language,
                    speed: 0.8,         // Slightly slower for better comprehension
                    model: 'tts-1-hd'   // Higher quality audio
                }),
            });

            const data = await response.json();
            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate audio');
            }

            console.log(`Playing audio for "${currentWord.word}" (${currentWord.language}) with voice "${data.voice}"`);

            if (audioPlayer) {
                audioPlayer.pause();
            }

            audioPlayer = new Audio(data.audio_url);
            await audioPlayer.play();
        } catch (error) {
            console.error('Audio playback failed:', error);
        }
    });

    // Navigation
    prevWordBtn.addEventListener('click', () => {
        if (currentMode) loadExercise(currentMode);
    });

    nextWordBtn.addEventListener('click', () => {
        if (currentMode) loadExercise(currentMode);
    });

    // Utility functions
    function shuffleArray(array) {
        for (let i = array.length - 1; i > 0; i--) {
            const j = Math.floor(Math.random() * (i + 1));
            [array[i], array[j]] = [array[j], array[i]];
        }
        return array;
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

        setTimeout(() => loadExercise(currentMode), 1500);
    };

    window.checkTypedAnswer = function(button) {
        const input = button.previousElementSibling;
        const userAnswer = input.value.trim().toLowerCase();
        const correctAnswer = currentWord.translation.toLowerCase();

        button.disabled = true;
        input.disabled = true;

        if (userAnswer === correctAnswer) {
            input.classList.add('is-valid');
            saveProgress(true);
        } else {
            input.classList.add('is-invalid');
            vocabularyExercise.insertAdjacentHTML('beforeend', 
                `<div class="mt-3">Correct answer: ${currentWord.translation}</div>`);
            saveProgress(false);
        }

        setTimeout(() => loadExercise(currentMode), 1500);
    };

    async function saveProgress(isCorrect) {
        try {
            await fetch('/api/vocabulary/progress', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
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
