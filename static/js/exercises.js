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

// Function to display the current exercise
function displayExercise() {
    const exerciseContainer = document.getElementById('exercise-container');
    const progressBar = document.getElementById('progress-bar');
    const exercise = exercises[currentExerciseIndex];

    // Update progress bar
    const progressPercentage = (currentExerciseIndex / exercises.length) * 100;
    progressBar.style.width = `${progressPercentage}%`;
    progressBar.setAttribute('aria-valuenow', progressPercentage);

    // Create exercise HTML
    let exerciseHTML = '';

    if (exercise.type === 'vocabulary') {
        exerciseHTML = `
            <h3>${exercise.question}</h3>
            <div class="options-container">
        `;

        exercise.options.forEach((option, index) => {
            exerciseHTML += `
                <div class="form-check">
                    <input class="form-check-input" type="radio" name="answer" id="option${index}" value="${option}">
                    <label class="form-check-label" for="option${index}">
                        ${option}
                    </label>
                </div>
            `;
        });

        exerciseHTML += `
            </div>
            <button class="btn btn-success mt-3" onclick="checkAnswer()">Check Answer</button>
        `;
    }

    exerciseContainer.innerHTML = exerciseHTML;
}

// Function to check answer
function checkAnswer() {
    const selectedOption = document.querySelector('input[name="answer"]:checked');

    if (!selectedOption) {
        alert('Please select an answer!');
        return;
    }

    const userAnswer = selectedOption.value;
    const correctAnswer = exercises[currentExerciseIndex].answer;

    if (userAnswer === correctAnswer) {
        score++;
        alert('Correct! 🎉');
    } else {
        alert(`Incorrect. The correct answer is: ${correctAnswer}`);
    }

    // Save progress to the server
    saveProgress();

    // Move to next exercise or show results
    nextExercise();
}

// Function to move to the next exercise
function nextExercise() {
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
            <h2>Exercise Complete!</h2>
            <p class="lead">Your score: ${score}/${exercises.length} (${percentage}%)</p>
            <button class="btn btn-primary mt-3" onclick="restartExercises()">Try Again</button>
        </div>
    `;
}

// Function to restart exercises
function restartExercises() {
    currentExerciseIndex = 0;
    score = 0;
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