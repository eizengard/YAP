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
        appendMessage('assistant', data.response);

        // Convert response to speech
        await textToSpeech(data.response);
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

function appendMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}-message`;
    messageDiv.textContent = content;
    chatMessages.appendChild(messageDiv);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

async function textToSpeech(text) {
    try {
        const response = await fetch('/api/text-to-speech', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ text }),
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.error || 'Text-to-speech failed');
        }

        const audio = new Audio(data.audio_path);
        await audio.play();
    } catch (error) {
        console.error('TTS error:', error);
        appendMessage('system', 'Failed to play audio');
    }
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