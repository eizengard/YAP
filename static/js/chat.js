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

        const response = await fetch('/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message }),
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Failed to get response');
        }

        // Add AI response to chat
        appendMessage('assistant', data.response, true); // Added true to indicate it's an AI response

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

        let audio = null;
        let isPlaying = false;

        playButton.onclick = async () => {
            try {
                if (!audio) {
                    // First time playing - fetch the audio
                    playButton.disabled = true;
                    const response = await fetch('/api/text-to-speech', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({ text: content }),
                    });

                    const data = await response.json();
                    if (!response.ok) {
                        throw new Error(data.error || 'Text-to-speech failed');
                    }

                    audio = new Audio(data.audio_url);

                    // Add audio event listeners
                    audio.onended = () => {
                        isPlaying = false;
                        playButton.innerHTML = '<i class="bi bi-volume-up"></i>';
                    };

                    audio.onerror = () => {
                        console.error("Audio playback failed");
                        appendMessage('system', 'Failed to play audio');
                        playButton.disabled = false;
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
                    }
                }
            } catch (error) {
                console.error('TTS error:', error);
                appendMessage('system', 'Failed to play audio');
            } finally {
                playButton.disabled = false;
            }
        };

        audioControls.appendChild(playButton);
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