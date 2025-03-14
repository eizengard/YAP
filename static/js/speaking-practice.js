document.addEventListener('DOMContentLoaded', () => {
    console.log('Speaking practice module loaded');
    
    // Add custom CSS to make sure practice area is properly visible
    const style = document.createElement('style');
    style.textContent = `
        #practice-area {
            position: relative;
            min-height: 300px;
            transition: opacity 0.3s ease;
        }
        #scenario-content {
            transition: opacity 0.3s ease;
            position: relative;
        }
        #loading-message {
            transition: opacity 0.3s ease;
        }
    `;
    document.head.appendChild(style);
    
    // Simple helper function to display status messages in the UI
    function showStatus(message, isError = false) {
        console.log(`Status: ${message}`);
        const statusArea = document.getElementById('status-area');
        if (statusArea) {
            const messageClass = isError ? 'alert-danger' : 'alert-info';
            statusArea.innerHTML = `
                <div class="alert ${messageClass} alert-dismissible fade show" role="alert">
                    ${message}
                    <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
                </div>
            `;
        }
    }
    
    // Get DOM elements - check if they exist
    const practiceArea = document.getElementById('practice-area');
    const scenarioContent = document.getElementById('scenario-content');
    const loadingMessage = document.getElementById('loading-message');

    if (!practiceArea) {
        console.error('practice-area element not found');
        showStatus('Critical error: practice-area not found', true);
    }
    if (!scenarioContent) {
        console.error('scenario-content element not found');
        showStatus('Critical error: scenario-content not found', true);
    }
    if (!loadingMessage) {
        console.error('loading-message element not found');
        showStatus('Critical error: loading-message not found', true);
    }

    // Global state variables
    let currentScenario = null;
    let currentScenarioId = null;
    let currentPromptIndex = 0;
    let prompts = [];
    let audioStream = null;
    let mediaRecorder = null;
    let audioChunks = [];
    let audioBlob = null;
    let audioUrl = null;
    let isRecording = false;
    let mockRecordingTimer = null;

    // Find all scenario buttons and attach event listeners
    const scenarioButtons = document.querySelectorAll('.start-scenario');
    console.log(`Found ${scenarioButtons.length} scenario buttons`);
    
    scenarioButtons.forEach(button => {
        button.addEventListener('click', () => {
            const scenarioId = button.getAttribute('data-scenario');
            if (scenarioId) {
                console.log(`Button clicked for scenario: ${scenarioId}`);
                showStatus(`Selected scenario: ${scenarioId}`);
                currentScenarioId = scenarioId;
                loadScenario(scenarioId);
            } else {
                console.error('Button missing data-scenario attribute');
                showStatus('Error: Button missing scenario ID', true);
            }
        });
    });
    
    // Look for the Start Practice button
    const startPracticeBtn = document.getElementById('start-practice');
    if (startPracticeBtn) {
        console.log('Found Start Practice button');
        startPracticeBtn.addEventListener('click', () => {
            console.log('Start Practice button clicked');
            showStatus('Starting practice session');
            // Use the first scenario as default or a predefined one
            const defaultScenario = 'travel'; // Set your default scenario ID here
            currentScenarioId = defaultScenario;
            loadScenario(defaultScenario);
        });
    } else {
        console.warn('Start Practice button not found - will use first scenario button as fallback');
        // If we have at least one scenario button, use the first one as a fallback
        if (scenarioButtons.length > 0) {
            const firstScenario = scenarioButtons[0].getAttribute('data-scenario');
            if (firstScenario) {
                scenarioButtons[0].click();
            }
        }
    }

    function loadScenario(scenarioId) {
        console.log(`Loading scenario with ID: ${scenarioId}`);
        showStatus(`Loading scenario: ${scenarioId}`);
        
        // Store scenario ID
        currentScenarioId = scenarioId;
        
        // Get DOM elements
        const practiceArea = document.getElementById('practice-area');
        const scenarioContent = document.getElementById('scenario-content');
        const loadingMessage = document.getElementById('loading-message');
        
        // Simple visibility management with display property
        if (practiceArea) practiceArea.style.display = 'block';
        if (scenarioContent) scenarioContent.style.display = 'none';
        if (loadingMessage) loadingMessage.style.display = 'block';
        
        console.log('Fetching scenario data...');
        
        // Fetch scenario data
        fetch(`/api/speaking/scenario/${scenarioId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Failed with status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                console.log('Scenario data received:', data);
                
                // Hide loading message, show content
                if (loadingMessage) loadingMessage.style.display = 'none';
                
                // Display scenario data
                displayScenario(data);
            })
            .catch(error => {
                console.error('Error fetching scenario:', error);
                
                // Try alternate endpoint
                fetch(`/api/scenarios/${scenarioId}`)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error('Both API endpoints failed');
                        }
                        return response.json();
                    })
                    .then(data => {
                        console.log('Data from alternate endpoint:', data);
                        
                        // Hide loading, show content
                        if (loadingMessage) loadingMessage.style.display = 'none';
                        
                        // Display scenario
                        displayScenario(data);
                    })
                    .catch(finalError => {
                        console.error('All endpoints failed:', finalError);
                        
                        // Hide loading message
                        if (loadingMessage) loadingMessage.style.display = 'none';
                        
                        // Show error message in scenario content
                        if (scenarioContent) {
                            scenarioContent.style.display = 'block';
                            scenarioContent.innerHTML = `
                                <div class="alert alert-danger">
                                    <h4>Error Loading Scenario</h4>
                                    <p>${finalError.message}</p>
                                    <button class="btn btn-primary mt-3" onclick="window.location.reload()">Retry</button>
                                </div>
                            `;
                        }
                    });
            });
    }

    // Check if browser supports audio recording
    function checkRecordingSupport() {
        return !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
    }
    
    // Function to start recording
    function startRecording() {
        console.log('Start recording button clicked');
        showStatus('Starting recording...');
        
        const startRecordingBtn = document.getElementById('startRecordingBtn');
        const stopRecordingBtn = document.getElementById('stopRecordingBtn');
        const recordingStatus = document.getElementById('recordingStatus');
        
        if (startRecordingBtn) startRecordingBtn.style.display = 'none';
        if (stopRecordingBtn) stopRecordingBtn.style.display = 'inline-block';
        if (recordingStatus) recordingStatus.style.display = 'block';
        
        // Check if recording is supported
        if (!checkRecordingSupport()) {
            console.log('Browser does not support recording - using mock recording');
            startMockRecording();
            return;
        }
        
        // Request microphone access
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                console.log('Microphone access granted');
                showStatus('Microphone access granted');
                
                // Store the stream for later use
                audioStream = stream;
                
                // Create media recorder
                mediaRecorder = new MediaRecorder(stream);
                audioChunks = [];
                
                // Collect audio chunks
                mediaRecorder.ondataavailable = (event) => {
                    if (event.data.size > 0) {
                        audioChunks.push(event.data);
                    }
                };
                
                // When recording stops
                mediaRecorder.onstop = () => {
                    console.log('Media recorder stopped');
                    
                    // Stop all tracks
                    if (audioStream) {
                        audioStream.getTracks().forEach(track => track.stop());
                    }
                    
                    // Create audio blob
                    audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
                    audioUrl = URL.createObjectURL(audioBlob);
                    
                    // Display audio playback
                    const audioPlayback = document.getElementById('audioPlayback');
                    const audioPlayer = document.getElementById('audioPlayer');
                    
                    if (audioPlayer) audioPlayer.src = audioUrl;
                    if (audioPlayback) audioPlayback.style.display = 'block';
                    
                    showStatus('Recording completed');
                };
                
                // Start recording with 10ms timeslice to get data frequently
                mediaRecorder.start(10);
                showStatus('Recording started');
            })
            .catch(error => {
                console.error('Error accessing microphone:', error);
                showStatus(`Error: Could not access microphone. ${error.message}`, true);
                
                // Start mock recording as fallback
                startMockRecording();
            });
    }
    
    // Function to start mock recording (for browsers without MediaRecorder support)
    function startMockRecording() {
        showStatus('Using simulated recording (no actual audio is captured)');
        isRecording = true;
        
        let recordingTime = 0;
        const recordingStatus = document.getElementById('recordingStatus');
        
        if (recordingStatus) {
            recordingStatus.innerHTML = 'Simulated Recording... (0s)';
        }
        
        // Simulate recording with a timer
        mockRecordingTimer = setInterval(() => {
            recordingTime++;
            if (recordingStatus) {
                recordingStatus.innerHTML = `Simulated Recording... (${recordingTime}s)`;
            }
        }, 1000);
    }
    
    // Function to stop recording
    function stopRecording() {
        console.log('Stop recording button clicked');
        
        // Reset UI
        const startRecordingBtn = document.getElementById('startRecordingBtn');
        const stopRecordingBtn = document.getElementById('stopRecordingBtn');
        const recordingStatus = document.getElementById('recordingStatus');
        
        if (startRecordingBtn) startRecordingBtn.style.display = 'inline-block';
        if (stopRecordingBtn) stopRecordingBtn.style.display = 'none';
        if (recordingStatus) recordingStatus.style.display = 'none';
        
        // If using mock recording
        if (mockRecordingTimer) {
            clearInterval(mockRecordingTimer);
            mockRecordingTimer = null;
            finishMockRecording();
            return;
        }
        
        // Stop recording if possible
        if (mediaRecorder && mediaRecorder.state !== 'inactive') {
            mediaRecorder.stop();
            showStatus('Stopping recording...');
        } else {
            showStatus('Error: No active recording', true);
        }
    }
    
    // Function to finish mock recording
    function finishMockRecording() {
        showStatus('Simulated recording completed');
        isRecording = false;
        
        // Create a mock audio blob (actually just an empty blob)
        audioBlob = new Blob(['mock audio data'], { type: 'text/plain' });
        
        // Display audio playback section
        const audioPlayback = document.getElementById('audioPlayback');
        if (audioPlayback) {
            audioPlayback.style.display = 'block';
            audioPlayback.innerHTML = `
                <h5>Your Recording (Simulated):</h5>
                <div class="alert alert-info">
                    <p>This is a simulated recording. No actual audio was captured because your browser doesn't support audio recording.</p>
                    <p>In a real recording, you would hear your audio here.</p>
                </div>
                <button id="submitRecordingBtn" class="btn btn-success mt-2">Submit Recording</button>
            `;
            
            // Reattach the submit button listener
            document.getElementById('submitRecordingBtn')?.addEventListener('click', submitRecording);
        }
    }
    
    // Function to submit recording
    function submitRecording() {
        console.log('Submit recording button clicked');
        
        if (!audioBlob) {
            showStatus('Error: No recording to submit', true);
            return;
        }
        
        showStatus('Submitting recording...');
        
        // If it's a mock recording, create a simulated submission
        if (mockRecordingTimer || (audioBlob.type === 'text/plain')) {
            console.log('Simulating submission response for mock recording');
            
            // Display a simulated feedback after a short delay
            setTimeout(() => {
                showStatus('Recording submitted successfully (simulated)');
                
                // Display feedback
                const feedbackContainer = document.getElementById('feedback-container');
                if (feedbackContainer) {
                    feedbackContainer.style.display = 'block';
                    const pronunciationScore = document.getElementById('pronunciation-score');
                    const feedbackText = document.getElementById('feedback-text');
                    
                    if (pronunciationScore) pronunciationScore.textContent = '7.5';
                    if (feedbackText) feedbackText.textContent = 'This is simulated feedback. In a real session, you would receive actual pronunciation feedback here.';
                }
            }, 1500);
            
            return;
        }
        
        // Create FormData for real recording
        const formData = new FormData();
        formData.append('audio', audioBlob, 'recording.wav');
        formData.append('scenario_id', currentScenarioId);
        
        // Submit to server
        fetch('/api/speaking/submit', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            showStatus('Recording submitted successfully');
            console.log('Submission successful:', data);
            
            // Display feedback
            const feedbackContainer = document.getElementById('feedback-container');
            if (feedbackContainer) {
                feedbackContainer.style.display = 'block';
                const pronunciationScore = document.getElementById('pronunciation-score');
                const feedbackText = document.getElementById('feedback-text');
                
                if (pronunciationScore) pronunciationScore.textContent = data.score || 'N/A';
                if (feedbackText) feedbackText.textContent = data.feedback || 'No detailed feedback available.';
            } else {
                showStatus('Warning: feedback-container not found', true);
            }
        })
        .catch(error => {
            console.error('Error submitting recording:', error);
            showStatus(`Error: ${error.message}`, true);
        });
    }

    function displayScenario(data) {
        console.log('Displaying scenario:', data);
        
        // Get DOM elements
        const scenarioContent = document.getElementById('scenario-content');
        
        if (!scenarioContent) {
            console.error('Scenario content element not found');
            return;
        }
        
        // Extract data
        let title = data.title || '';
        let description = data.description || '';
        let prompt = '';
        
        // Handle different API response formats
        if (data.prompts && Array.isArray(data.prompts) && data.prompts.length > 0) {
            prompt = data.prompts[0];
            currentPromptIndex = 0;
            prompts = data.prompts;
            currentScenario = data;
        } else {
            prompt = data.prompt || '';
        }
        
        // Build HTML
        const html = `
            <div class="card mb-4">
                <div class="card-header bg-info text-white">
                    <h3>${title}</h3>
                </div>
                <div class="card-body">
                    <p>${description}</p>
                    <div class="card mb-3">
                        <div class="card-header">Prompt:</div>
                        <div class="card-body">
                            <p>${prompt}</p>
                        </div>
                    </div>
                    <div class="mt-4">
                        <button id="startRecordingBtn" class="btn btn-primary mb-3">
                            <i class="bi bi-mic-fill"></i> Start Recording
                        </button>
                        <button id="stopRecordingBtn" class="btn btn-danger mb-3" style="display: none;">
                            <i class="bi bi-stop-fill"></i> Stop Recording
                        </button>
                        <div id="recordingStatus" class="alert alert-info" style="display: none;">Recording...</div>
                        <div id="audioPlayback" class="mt-3" style="display: none;">
                            <h5>Your Recording:</h5>
                            <audio id="audioPlayer" controls></audio>
                            <button id="submitRecordingBtn" class="btn btn-success mt-2">Submit Recording</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Update DOM
        scenarioContent.innerHTML = html;
        scenarioContent.style.display = 'block';
        
        // Check if browser supports recording
        if (!checkRecordingSupport()) {
            showStatus('Your browser does not support audio recording. Using simulated recording mode.', true);
            const browserWarning = document.createElement('div');
            browserWarning.className = 'alert alert-warning';
            browserWarning.innerHTML = `
                <h5>Browser Compatibility Issue</h5>
                <p>Your browser does not support audio recording. The app will use a simulated recording mode instead.</p>
                <p>For best experience with real audio recording, please use Chrome or Firefox.</p>
            `;
            scenarioContent.prepend(browserWarning);
        }
        
        // Directly attach event listeners to buttons
        document.getElementById('startRecordingBtn')?.addEventListener('click', startRecording);
        document.getElementById('stopRecordingBtn')?.addEventListener('click', stopRecording);
        document.getElementById('submitRecordingBtn')?.addEventListener('click', submitRecording);
        
        // Update navigation buttons
        const prevExerciseBtn = document.getElementById('prev-exercise');
        const nextExerciseBtn = document.getElementById('next-exercise');
        
        if (prevExerciseBtn) {
            prevExerciseBtn.onclick = () => {
                if (currentPromptIndex > 0) {
                    currentPromptIndex--;
                    updatePrompt();
                }
            };
            prevExerciseBtn.disabled = currentPromptIndex === 0;
        }
        
        if (nextExerciseBtn) {
            nextExerciseBtn.onclick = () => {
                if (prompts && prompts.length > 0 && currentPromptIndex < prompts.length - 1) {
                    currentPromptIndex++;
                    updatePrompt();
                }
            };
            nextExerciseBtn.disabled = !prompts || prompts.length === 0 || currentPromptIndex >= prompts.length - 1;
        }
        
        console.log('Scenario displayed successfully');
    }

    // Helper function to update just the prompt text
    function updatePrompt() {
        if (!prompts || !prompts[currentPromptIndex]) return;
        
        const promptElement = document.querySelector('.card-body .card .card-body p');
        if (promptElement) {
            promptElement.textContent = prompts[currentPromptIndex];
        }
        
        // Update navigation buttons
        const prevExerciseBtn = document.getElementById('prev-exercise');
        const nextExerciseBtn = document.getElementById('next-exercise');
        
        if (prevExerciseBtn) {
            prevExerciseBtn.disabled = currentPromptIndex === 0;
        }
        
        if (nextExerciseBtn) {
            nextExerciseBtn.disabled = currentPromptIndex >= prompts.length - 1;
        }
    }
});