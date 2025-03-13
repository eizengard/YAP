// Exercise data
const exercises = [
    {
        id: 'vocab_1',
        type: 'vocabulary',
        question: 'What is the English word for "casa"?',
        options: ['House', 'Car', 'Book', 'Dog'],
        answer: 'House'
    },
    {
        id: 'vocab_2',
        type: 'vocabulary',
        question: 'What is the English word for "libro"?',
        options: ['Pencil', 'Book', 'Table', 'Computer'],
        answer: 'Book'
    },
    {
        id: 'vocab_3',
        type: 'vocabulary',
        question: 'What is the English word for "perro"?',
        options: ['Cat', 'Bird', 'Dog', 'Fish'],
        answer: 'Dog'
    }
];

let currentExerciseIndex = 0;
let score = 0;
let answerChecked = false;

// Function to display the current practice exercise
function displayExercise() {
    const exerciseContainer = document.getElementById('exercise-container');
    const progressBar = document.getElementById('progress-bar');
    const exercise = exercises[currentExerciseIndex];
    answerChecked = false;

    // Update progress bar
    const progressPercentage = (currentExerciseIndex / exercises.length) * 100;
    progressBar.style.width = `${progressPercentage}%`;
    progressBar.setAttribute('aria-valuenow', progressPercentage);

    // Create exercise HTML
    let exerciseHTML = `
        <div class="feedback-message" style="display: none;"></div>
        <div class="exercise-content">
            <h3>${exercise.question}</h3>
            <div class="options-container">
    `;

    exercise.options.forEach((option, index) => {
        exerciseHTML += `
            <div class="form-check option-row" onclick="selectOption(${index})">
                <input class="form-check-input" type="radio" name="answer" id="option${index}" value="${option}">
                <label class="form-check-label" for="option${index}">
                    ${option}
                </label>
            </div>
        `;
    });

    exerciseHTML += `
            </div>
            <div class="mt-3 text-center">
                <button class="btn btn-info" onclick="checkAnswer()">Check Answer</button>
            </div>
        </div>
    `;

    exerciseContainer.innerHTML = exerciseHTML;
}

// Function to select an option when clicking anywhere in the option row
function selectOption(index) {
    const radio = document.getElementById(`option${index}`);
    if (!radio.disabled) {
        radio.checked = true;
    }
}

// Function to show feedback message
function showFeedback(message, isCorrect) {
    const feedbackDiv = document.querySelector('.feedback-message');
    feedbackDiv.className = `feedback-message alert ${isCorrect ? 'alert-success' : 'alert-danger'} mb-3`;
    feedbackDiv.style.display = 'block';
    feedbackDiv.textContent = message;

    if (isCorrect) {
        // Trigger confetti
        confetti({
            particleCount: 100,
            spread: 70,
            origin: { y: 0.6 }
        });
    }
}

// Function to check answer
function checkAnswer() {
    const selectedOption = document.querySelector('input[name="answer"]:checked');

    if (!selectedOption) {
        showFeedback('Please select an answer!', false);
        return;
    }

    const userAnswer = selectedOption.value;
    const correctAnswer = exercises[currentExerciseIndex].answer;
    answerChecked = true;

    if (userAnswer === correctAnswer) {
        score++;
        showFeedback('Correct! 🎉', true);
    } else {
        showFeedback(`Incorrect. The correct answer is: ${correctAnswer}`, false);
    }

    // Disable radio buttons after checking
    document.querySelectorAll('input[name="answer"]').forEach(input => {
        input.disabled = true;
    });

    // Save progress to the server
    saveProgress();
}

// Function to move to the next exercise
function nextExercise() {
    if (!answerChecked) {
        showFeedback('Please check your answer before moving to the next question!', false);
        return;
    }

    if (currentExerciseIndex < exercises.length - 1) {
        currentExerciseIndex++;
        displayExercise();
    } else {
        showResults();
    }
}

// Function to show final results
function showResults() {
    const exerciseContainer = document.getElementById('exercise-container');
    const progressBar = document.getElementById('progress-bar');

    progressBar.style.width = '100%';
    progressBar.setAttribute('aria-valuenow', 100);

    const percentage = Math.round((score / exercises.length) * 100);

    exerciseContainer.innerHTML = `
        <div class="text-center">
            <h2>Practice Complete!</h2>
            <p class="lead">Your score: ${score}/${exercises.length} (${percentage}%)</p>
            <button class="btn btn-info mt-3" onclick="restartExercises()">Try Again</button>
        </div>
    `;

    if (percentage >= 80) {
        confetti({
            particleCount: 200,
            spread: 90,
            origin: { y: 0.6 }
        });
    }
}

// Function to restart exercises
function restartExercises() {
    currentExerciseIndex = 0;
    score = 0;
    answerChecked = false;
    displayExercise();
}

// Function to save progress to server
async function saveProgress() {
    try {
        const response = await fetch('/api/save-progress', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                exercise_id: exercises[currentExerciseIndex].id,
                score: score
            }),
        });

        if (!response.ok) {
            console.error('Failed to save progress');
        }
    } catch (error) {
        console.error('Error saving progress:', error);
    }
}

// Initialize exercises when page loads
document.addEventListener('DOMContentLoaded', () => {
    displayExercise();
});