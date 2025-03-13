document.addEventListener('DOMContentLoaded', () => {
    let mediaRecorder;
    let audioChunks = [];
    let recordingTimer;
    let currentScenario = null;
    let recordedBlob = null;
    let currentPromptIndex = 0;
    let prompts = [];

    const startRecordingBtn = document.getElementById('start-recording');
    const stopRecordingBtn = document.getElementById('stop-recording');
    const playRecordingBtn = document.getElementById('play-recording');
    const playExampleBtn = document.getElementById('play-example');
    const recordingTimerDisplay = document.getElementById('recording-timer');
    const practiceArea = document.getElementById('practice-area');
    const nextExerciseBtn = document.getElementById('next-exercise');
    const prevExerciseBtn = document.getElementById('prev-exercise');

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
            prompts = data.prompts;
            currentPromptIndex = 0;
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
        document.getElementById('scenario-description').textContent = 
            `${scenario.description}\n\nPrompt: ${prompts[currentPromptIndex]}`;

        // Reset recording interface
        stopRecordingBtn.disabled = true;
        playRecordingBtn.disabled = true;
        startRecordingBtn.disabled = false;
        document.getElementById('feedback-area').style.display = 'none';
        document.getElementById('hint-area').style.display = 'none';

        // Update navigation buttons
        prevExerciseBtn.disabled = currentPromptIndex === 0;
        nextExerciseBtn.disabled = currentPromptIndex === prompts.length - 1;
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
        if (currentScenario && prompts[currentPromptIndex]) {
            playExampleBtn.disabled = true;
            await generateAndPlayExample(prompts[currentPromptIndex], currentScenario.target_language);
            playExampleBtn.disabled = false;
        }
    });

    nextExerciseBtn.addEventListener('click', () => {
        if (currentPromptIndex < prompts.length - 1) {
            currentPromptIndex++;
            displayScenario(currentScenario);
        }
    });

    prevExerciseBtn.addEventListener('click', () => {
        if (currentPromptIndex > 0) {
            currentPromptIndex--;
            displayScenario(currentScenario);
        }
    });

    async function submitRecording(blob) {
        try {
            const formData = new FormData();
            formData.append('audio', blob);
            formData.append('scenario_id', currentScenario.id);
            formData.append('prompt_index', currentPromptIndex);

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

        // Display detailed feedback
        feedbackContent.innerHTML = `
            <div class="mt-3">
                <h6>Pronunciation Feedback:</h6>
                <p>${feedback.pronunciation_feedback}</p>

                <h6>Grammar Feedback:</h6>
                <p>${feedback.grammar_feedback}</p>

                <h6>Vocabulary Feedback:</h6>
                <p>${feedback.vocabulary_feedback}</p>

                <h6>Fluency Score: ${Math.round(feedback.fluency_score)}%</h6>

                <h6>Suggestions for Improvement:</h6>
                <ul>
                    ${feedback.improvement_suggestions.map(suggestion => `<li>${suggestion}</li>`).join('')}
                </ul>

                <h6>Example Response:</h6>
                <p class="text-success">${feedback.correct_response_example}</p>
            </div>
        `;

        feedbackArea.style.display = 'block';

        // If the score is good, show confetti
        if (feedback.pronunciation_score >= 80) {
            confetti({
                particleCount: 100,
                spread: 70,
                origin: { y: 0.6 }
            });
        }
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

    // Add this function after the playExampleBtn click event handler
    async function generateAndPlayExample(text, language) {
        try {
            const response = await fetch('/api/speaking/example-audio', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ 
                    text: text,
                    language: language
                }),
            });

            if (!response.ok) {
                throw new Error('Failed to generate example audio');
            }

            const data = await response.json();
            const audio = new Audio(data.audio_url);
            await audio.play();
        } catch (error) {
            console.error('Error playing example:', error);
            alert('Failed to play example audio. Please try again.');
        }
    }

    // Initialize hint button
    const showHintBtn = document.getElementById('show-hint');
    const hintArea = document.getElementById('hint-area');

    showHintBtn.addEventListener('click', () => {
        if (currentScenario && currentScenario.hints && currentScenario.hints[currentPromptIndex]) {
            const hints = currentScenario.hints[currentPromptIndex].split(' / ');
            hintArea.innerHTML = `
                <h6>Suggested Responses:</h6>
                <ul class="mb-0">
                    ${hints.map(hint => `<li>${hint}</li>`).join('')}
                </ul>
            `;
            hintArea.style.display = 'block';
        }
    });
});