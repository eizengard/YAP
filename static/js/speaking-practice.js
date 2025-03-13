document.addEventListener('DOMContentLoaded', () => {
    let mediaRecorder;
    let audioChunks = [];
    let recordingTimer;
    let currentScenario = null;
    let recordedBlob = null;

    const startRecordingBtn = document.getElementById('start-recording');
    const stopRecordingBtn = document.getElementById('stop-recording');
    const playRecordingBtn = document.getElementById('play-recording');
    const playExampleBtn = document.getElementById('play-example');
    const recordingTimerDisplay = document.getElementById('recording-timer');
    const practiceArea = document.getElementById('practice-area');

    // Initialize scenario buttons
    document.querySelectorAll('.start-scenario').forEach(button => {
        button.addEventListener('click', () => {
            const scenario = button.dataset.scenario;
            loadScenario(scenario);
        });
    });

    async function loadScenario(scenarioId) {
        try {
            const response = await fetch(`/api/speaking/scenario/${scenarioId}`);
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to load scenario');
            }

            currentScenario = data;
            displayScenario(data);
            practiceArea.style.display = 'block';
            
            // Scroll to practice area
            practiceArea.scrollIntoView({ behavior: 'smooth' });
        } catch (error) {
            console.error('Failed to load scenario:', error);
            alert('Failed to load the practice scenario. Please try again.');
        }
    }

    function displayScenario(scenario) {
        document.getElementById('scenario-title').textContent = scenario.title;
        document.getElementById('scenario-description').textContent = scenario.description;
        
        // Reset recording interface
        stopRecordingBtn.disabled = true;
        playRecordingBtn.disabled = true;
        startRecordingBtn.disabled = false;
        document.getElementById('feedback-area').style.display = 'none';
    }

    // Recording functionality
    startRecordingBtn.addEventListener('click', async () => {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            audioChunks = [];
            mediaRecorder = new MediaRecorder(stream);

            mediaRecorder.addEventListener('dataavailable', event => {
                audioChunks.push(event.data);
            });

            mediaRecorder.addEventListener('stop', () => {
                recordedBlob = new Blob(audioChunks, { type: 'audio/webm' });
                playRecordingBtn.disabled = false;
                submitRecording(recordedBlob);
            });

            // Start recording
            mediaRecorder.start();
            startRecordingBtn.disabled = true;
            stopRecordingBtn.disabled = false;
            recordingTimerDisplay.style.display = 'inline-block';
            startTimer();

        } catch (error) {
            console.error('Error accessing microphone:', error);
            alert('Unable to access microphone. Please ensure you have granted microphone permissions.');
        }
    });

    stopRecordingBtn.addEventListener('click', () => {
        if (mediaRecorder && mediaRecorder.state === 'recording') {
            mediaRecorder.stop();
            stopRecordingBtn.disabled = true;
            startRecordingBtn.disabled = false;
            clearInterval(recordingTimer);
            recordingTimerDisplay.style.display = 'none';
        }
    });

    playRecordingBtn.addEventListener('click', () => {
        if (recordedBlob) {
            const audio = new Audio(URL.createObjectURL(recordedBlob));
            audio.play();
        }
    });

    playExampleBtn.addEventListener('click', async () => {
        if (currentScenario && currentScenario.example_audio_url) {
            const audio = new Audio(currentScenario.example_audio_url);
            await audio.play();
        }
    });

    async function submitRecording(blob) {
        try {
            const formData = new FormData();
            formData.append('audio', blob);
            formData.append('scenario_id', currentScenario.id);

            const response = await fetch('/api/speaking/submit', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to submit recording');
            }

            displayFeedback(data);
        } catch (error) {
            console.error('Failed to submit recording:', error);
            alert('Failed to submit recording. Please try again.');
        }
    }

    function displayFeedback(feedback) {
        const feedbackArea = document.getElementById('feedback-area');
        const progressBar = document.getElementById('pronunciation-progress');
        const feedbackContent = document.getElementById('pronunciation-feedback');

        // Update progress bar
        progressBar.style.width = `${feedback.pronunciation_score}%`;
        progressBar.setAttribute('aria-valuenow', feedback.pronunciation_score);
        progressBar.textContent = `${Math.round(feedback.pronunciation_score)}%`;

        // Display feedback text
        feedbackContent.innerHTML = `
            <div class="mt-3">
                <h6>Pronunciation Feedback:</h6>
                <p>${feedback.feedback}</p>
            </div>
        `;

        feedbackArea.style.display = 'block';
    }

    function startTimer() {
        let seconds = 0;
        recordingTimer = setInterval(() => {
            seconds++;
            const minutes = Math.floor(seconds / 60);
            const remainingSeconds = seconds % 60;
            recordingTimerDisplay.textContent = 
                `Recording: ${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
        }, 1000);
    }
});
