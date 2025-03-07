// Voice handling functionality for language learning app
class VoiceHandler {
    constructor() {
        this.recognition = null;
        this.synthesis = window.speechSynthesis;
        this.isListening = false;
        this.audioContext = null;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.stream = null;
        
        this.initializeSpeechRecognition();
    }

    initializeSpeechRecognition() {
        if ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            this.recognition = new SpeechRecognition();
            this.recognition.continuous = false;
            this.recognition.interimResults = false;
            this.recognition.lang = 'en-US'; // Default language
            
            this.setupRecognitionHandlers();
        }
    }

    setupRecognitionHandlers() {
        this.recognition.onstart = () => {
            this.isListening = true;
            this.dispatchEvent('voiceStart');
        };

        this.recognition.onend = () => {
            this.isListening = false;
            this.dispatchEvent('voiceEnd');
        };

        this.recognition.onerror = (event) => {
            console.error('Speech recognition error:', event.error);
            this.dispatchEvent('voiceError', event.error);
        };

        this.recognition.onresult = (event) => {
            const transcript = event.results[0][0].transcript;
            this.dispatchEvent('voiceResult', transcript);
        };
    }

    async startRecording() {
        try {
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }

            this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            this.mediaRecorder = new MediaRecorder(this.stream);
            this.audioChunks = [];

            this.mediaRecorder.ondataavailable = (event) => {
                if (event.data.size > 0) {
                    this.audioChunks.push(event.data);
                }
            };

            this.mediaRecorder.onstop = async () => {
                const audioBlob = new Blob(this.audioChunks, { type: 'audio/wav' });
                await this.handleRecordingComplete(audioBlob);
            };

            this.mediaRecorder.start();
            this.dispatchEvent('recordingStart');
        } catch (error) {
            console.error('Error starting recording:', error);
            this.dispatchEvent('recordingError', error.message);
        }
    }

    stopRecording() {
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();
            this.stream.getTracks().forEach(track => track.stop());
            this.dispatchEvent('recordingStop');
        }
    }

    async handleRecordingComplete(audioBlob) {
        try {
            const formData = new FormData();
            formData.append('audio', audioBlob);

            const response = await fetch('/api/transcribe', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Transcription failed');
            }

            const data = await response.json();
            this.dispatchEvent('transcriptionComplete', data.text);
        } catch (error) {
            console.error('Transcription error:', error);
            this.dispatchEvent('transcriptionError', error.message);
        }
    }

    async speak(text, language = 'en-US') {
        return new Promise((resolve, reject) => {
            if (!this.synthesis) {
                reject(new Error('Speech synthesis not supported'));
                return;
            }

            const utterance = new SpeechSynthesisUtterance(text);
            utterance.lang = language;
            utterance.rate = 1.0;
            utterance.pitch = 1.0;

            utterance.onend = () => {
                this.dispatchEvent('speakEnd');
                resolve();
            };

            utterance.onerror = (error) => {
                this.dispatchEvent('speakError', error);
                reject(error);
            };

            this.synthesis.speak(utterance);
            this.dispatchEvent('speakStart');
        });
    }

    cancelSpeech() {
        if (this.synthesis) {
            this.synthesis.cancel();
        }
    }

    dispatchEvent(eventName, data = null) {
        const event = new CustomEvent('voice:' + eventName, {
            detail: data,
            bubbles: true
        });
        document.dispatchEvent(event);
    }

    setLanguage(language) {
        if (this.recognition) {
            this.recognition.lang = language;
        }
    }
}

// Create and export voice handler instance
const voiceHandler = new VoiceHandler();

// Event listeners for UI integration
document.addEventListener('DOMContentLoaded', () => {
    const voiceButton = document.getElementById('voice-button');
    if (voiceButton) {
        voiceButton.addEventListener('click', () => {
            if (!voiceHandler.isListening) {
                voiceHandler.startRecording();
                voiceButton.classList.add('recording');
            } else {
                voiceHandler.stopRecording();
                voiceButton.classList.remove('recording');
            }
        });
    }

    // Voice event handlers
    document.addEventListener('voice:recordingStart', () => {
        console.log('Recording started');
    });

    document.addEventListener('voice:recordingStop', () => {
        console.log('Recording stopped');
    });

    document.addEventListener('voice:transcriptionComplete', (event) => {
        const chatInput = document.getElementById('chat-input');
        if (chatInput && event.detail) {
            chatInput.value = event.detail;
        }
    });

    document.addEventListener('voice:transcriptionError', (event) => {
        console.error('Transcription error:', event.detail);
    });
});

export default voiceHandler;
