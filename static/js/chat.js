document.addEventListener('DOMContentLoaded', async () => {
    // Load chat history when page loads
    try {
        const response = await fetch('/api/chat/history');
        const data = await response.json();
        if (response.ok) {
            data.history.reverse().forEach(chat => {
                appendMessage('user', chat.message);
                appendMessage('assistant', chat.response);
            });
        }
    } catch (error) {
        console.error('Failed to load chat history:', error);
    }
});

const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatMessages = document.getElementById('chat-messages');
const voiceButton = document.getElementById('voice-button');

let isRecording = false;
let mediaRecorder = null;
let audioChunks = [];

// Chat form submit handler
chatForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const message = chatInput.value.trim();
    if (!message) return;

    // Add user message to chat
    appendMessage('user', message);
    chatInput.value = '';

    try {
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

        appendMessage('assistant', data.response);
        // Convert response to speech
        await textToSpeech(data.response);
    } catch (error) {
        console.error('Chat error:', error);
        appendMessage('system', `Error: ${error.message}`);
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
        if (response.ok) {
            const audio = new Audio(data.audio_path);
            audio.play();
        } else {
            throw new Error(data.error || 'Text-to-speech failed');
        }
    } catch (error) {
        console.error('TTS error:', error);
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
                    if (response.ok) {
                        chatInput.value = data.text;
                    } else {
                        throw new Error(data.error || 'Transcription failed');
                    }
                } catch (error) {
                    console.error('Transcription error:', error);
                }
            };

            mediaRecorder.start();
            isRecording = true;
            voiceButton.textContent = 'Stop Recording';
            voiceButton.classList.add('recording');
        } catch (error) {
            console.error('Recording error:', error);
        }
    } else {
        mediaRecorder.stop();
        isRecording = false;
        voiceButton.textContent = 'Start Recording';
        voiceButton.classList.remove('recording');
    }
});