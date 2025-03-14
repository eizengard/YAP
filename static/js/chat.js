document.addEventListener('DOMContentLoaded', async () => {
    await loadChatHistory();
});

const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatMessages = document.getElementById('chat-messages');
const newChatBtn = document.getElementById('new-chat-btn');
const voiceButton = document.getElementById('voice-button');

let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];

async function loadChatHistory() {
    try {
        const response = await fetch('/api/chat/history');
        const data = await response.json();
        if (response.ok) {
            chatMessages.innerHTML = ''; // Clear existing messages
            data.history.reverse().forEach(chat => {
                appendMessage('user', chat.message);
                appendMessage('assistant', chat.response);
            });
        } else {
            throw new Error(data.error || 'Failed to load chat history');
        }
    } catch (error) {
        console.error('Failed to load chat history:', error);
        appendMessage('system', 'Failed to load chat history');
    }
}

// New chat button handler
newChatBtn.addEventListener('click', () => {
    chatMessages.innerHTML = ''; // Clear the chat messages
    chatInput.value = ''; // Clear input field
    chatInput.focus(); // Focus on input field
});

// Chat form submit handler
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    try {
        // Disable form while processing
        chatInput.disabled = true;
        const submitBtn = chatForm.querySelector('button[type="submit"]');
        submitBtn.disabled = true;

        // Add user message to chat
        appendMessage('user', message);
        chatInput.value = '';

        // Get CSRF token from meta tag
        const csrfToken = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content');
        if (!csrfToken) {
            console.warn('CSRF token not found. Request may fail.');
        }

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': csrfToken || ''
            },
            body: JSON.stringify({ message }),
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Failed to get response');
        }

        // Add AI response to chat
        // Check if the response is a dictionary with content field or just a string
        let responseContent = data.response;
        if (typeof responseContent === 'object' && responseContent.content) {
            responseContent = responseContent.content;
        }
        
        appendMessage('assistant', responseContent, true);

    } catch (error) {
        console.error('Chat error:', error);
        appendMessage('system', `Error: ${error.message}`);
    } finally {
        // Re-enable form
        chatInput.disabled = false;
        chatForm.querySelector('button[type="submit"]').disabled = false;
        chatInput.focus();
    }
});

// Audio playback handling
function appendMessage(role, content, canSpeak = false) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;

    // Create message content
    const textSpan = document.createElement('span');
    textSpan.textContent = content;
    messageDiv.appendChild(textSpan);

    // Add speak button for AI responses
    if (canSpeak) {
        const audioControls = document.createElement('div');
        audioControls.className = 'audio-controls';

        const playButton = document.createElement('button');
        playButton.className = 'btn btn-sm btn-secondary ms-2';
        playButton.innerHTML = '<i class="bi bi-volume-up"></i>';

        // Add translate button
        const translateButton = document.createElement('button');
        translateButton.className = 'btn btn-sm btn-info ms-2';
        translateButton.innerHTML = '<i class="bi bi-translate"></i>';
        translateButton.title = 'Translate';

        let audio = null;
        let isPlaying = false;
        let isTranslated = false;
        let originalText = content;
        
        // Handle translation
        translateButton.onclick = async () => {
            try {
                translateButton.disabled = true;
                
                if (!isTranslated) {
                    translateButton.innerHTML = '<i class="bi bi-hourglass-split"></i>';
                    
                    // Get CSRF token from meta tag
                    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
                    
                    // Detect language of the content
                    const hasSpanish = /[áéíóúñ¿¡]/i.test(content) || /hola|gracias|por favor/i.test(content);
                    const hasItalian = /[àèéìíòóùú]/i.test(content) || /ciao|grazie|prego/i.test(content);
                    const hasFrench = /[àâäæçéèêëîïôœùûüÿ]/i.test(content) || /bonjour|merci|s'il vous plaît/i.test(content);
                    const hasGerman = /[äöüß]/i.test(content) || /guten tag|danke|bitte/i.test(content);
                    
                    // Default to assuming English if no other language markers are found
                    let sourceLang = 'en';
                    let targetLang = 'en'; // Will be updated
                    
                    if (hasSpanish) {
                        sourceLang = 'es';
                        targetLang = 'en'; // Translate from Spanish to English
                    } else if (hasItalian) {
                        sourceLang = 'it';
                        targetLang = 'en'; // Translate from Italian to English
                    } else if (hasFrench) {
                        sourceLang = 'fr';
                        targetLang = 'en'; // Translate from French to English
                    } else if (hasGerman) {
                        sourceLang = 'de';
                        targetLang = 'en'; // Translate from German to English
                    } else {
                        // If the text is in English, translate to the user's learning language
                        // First try to get user's current language from the page if available
                        const langBadge = document.querySelector('.badge.bg-primary[data-lang]');
                        if (langBadge) {
                            targetLang = langBadge.dataset.lang;
                        } else {
                            // Default to Spanish if we can't detect
                            targetLang = 'es';
                        }
                    }
                    
                    const response = await fetch('/api/translate', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken || ''
                        },
                        body: JSON.stringify({ 
                            text: content,
                            source_lang: sourceLang,
                            target_lang: targetLang
                        }),
                    });

                    const data = await response.json();
                    if (!response.ok) {
                        throw new Error(data.error || 'Translation failed');
                    }

                    textSpan.textContent = data.translated_text;
                    isTranslated = true;
                    translateButton.innerHTML = '<i class="bi bi-translate"></i> Original';
                } else {
                    // Switch back to original text
                    textSpan.textContent = originalText;
                    isTranslated = false;
                    translateButton.innerHTML = '<i class="bi bi-translate"></i>';
                }
            } catch (error) {
                console.error('Translation error:', error);
                textSpan.textContent = originalText;
                translateButton.innerHTML = '<i class="bi bi-translate"></i>';
                // Show error message in a small popup within the message
                const errorMsg = document.createElement('div');
                errorMsg.className = 'text-danger small mt-1';
                errorMsg.textContent = `Translation error: ${error.message}`;
                messageDiv.appendChild(errorMsg);
                setTimeout(() => errorMsg.remove(), 5000); // Remove after 5 seconds
            } finally {
                translateButton.disabled = false;
            }
        };

        playButton.onclick = async () => {
            try {
                if (!audio) {
                    // First time playing - fetch the audio
                    playButton.disabled = true;
                    playButton.innerHTML = '<i class="bi bi-hourglass-split"></i>';

                    // Detect if the text contains mostly Spanish or Italian words
                    const hasSpanish = /[áéíóúñ¿¡]/i.test(content) || /hola|gracias|por favor/i.test(content);
                    const hasItalian = /[àèéìíòóùú]/i.test(content) || /ciao|grazie|prego/i.test(content);
                    
                    // Determine likely language for TTS
                    let lang = 'en';    // Default to English
                    if (hasSpanish) {
                        lang = 'es';    // Spanish
                    } else if (hasItalian) {
                        lang = 'it';    // Italian
                    }

                    // Get CSRF token from meta tag
                    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');

                    const response = await fetch('/api/text-to-speech', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': csrfToken
                        },
                        body: JSON.stringify({ 
                            text: content,
                            lang: lang,  // Pass detected language
                            speed: 0.8,  // Slightly slower for better comprehension
                            model: 'tts-1-hd'  // Higher quality audio
                        }),
                    });

                    const data = await response.json();
                    if (!response.ok) {
                        console.error('TTS error:', data.error);
                        throw new Error(data.error || 'Text-to-speech failed');
                    }

                    console.log(`Playing audio in ${lang} with voice "${data.voice}"`);
                    audio = new Audio(data.audio_url);

                    // Add audio event listeners
                    audio.onended = () => {
                        isPlaying = false;
                        playButton.innerHTML = '<i class="bi bi-volume-up"></i>';
                    };

                    audio.onerror = (e) => {
                        console.error("Audio playback failed", e);
                        appendMessage('system', 'Failed to play audio: ' + (e.message || 'Unknown error'));
                        playButton.disabled = false;
                        playButton.innerHTML = '<i class="bi bi-volume-up"></i>';
                    };

                    // Add progress indicator
                    audio.onprogress = () => {
                        if (isPlaying) {
                            playButton.innerHTML = '<i class="bi bi-pause-fill"></i>';
                        }
                    };
                }

                if (isPlaying) {
                    // Pause the audio
                    audio.pause();
                    isPlaying = false;
                    playButton.innerHTML = '<i class="bi bi-volume-up"></i>';
                } else {
                    // Play the audio
                    try {
                        await audio.play();
                        isPlaying = true;
                        playButton.innerHTML = '<i class="bi bi-pause-fill"></i>';
                    } catch (error) {
                        console.error("Audio playback failed:", error);
                        appendMessage('system', 'Failed to play audio');
                        playButton.innerHTML = '<i class="bi bi-volume-up"></i>';
                    }
                }
            } catch (error) {
                console.error('TTS error:', error);
                appendMessage('system', 'Failed to play audio');
                playButton.innerHTML = '<i class="bi bi-volume-up"></i>';
            } finally {
                playButton.disabled = false;
            }
        };

        audioControls.appendChild(playButton);
        audioControls.appendChild(translateButton);
        messageDiv.appendChild(audioControls);
    }

    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Voice recording functionality
voiceButton.addEventListener('click', async () => {
    if (!isRecording) {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];

            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                const formData = new FormData();
                formData.append('audio', audioBlob);

                try {
                    const response = await fetch('/api/transcribe', {
                        method: 'POST',
                        body: formData,
                    });

                    const data = await response.json();
                    if (!response.ok) {
                        throw new Error(data.error || 'Transcription failed');
                    }

                    chatInput.value = data.text;
                } catch (error) {
                    console.error('Transcription error:', error);
                    appendMessage('system', `Error: ${error.message}`);
                }
            };

            mediaRecorder.start();
            isRecording = true;
            voiceButton.classList.add('recording');
        } catch (error) {
            console.error('Recording error:', error);
            appendMessage('system', 'Failed to start recording');
        }
    } else {
        mediaRecorder.stop();
        isRecording = false;
        voiceButton.classList.remove('recording');
    }
});

function textToSpeech(text, voice = 'nova') {
    // Get CSRF token from meta tag
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    
    fetch('/api/text-to-speech', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            text: text,
            voice: voice
        }),
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            console.error('Error:', data.error);
            return;
        }
        
        // Play the audio
        const audio = new Audio(data.audio_url);
        audio.play();
    })
    .catch(error => {
        console.error('Error:', error);
    });
}