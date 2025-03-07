const exercises = [
    {
        id: 'vocab-1',
        type: 'vocabulary',
        words: ['hello', 'goodbye', 'thank you', 'please'],
        translations: ['hola', 'adiós', 'gracias', 'por favor']
    },
    {
        id: 'grammar-1',
        type: 'grammar',
        sentences: ['I am learning Spanish', 'She speaks English'],
        correct: ['Estoy aprendiendo español', 'Ella habla inglés']
    }
];

let currentExercise = 0;
let score = 0;

function loadExercise() {
    const exercise = exercises[currentExercise];
    const exerciseContainer = document.getElementById('exercise-container');
    exerciseContainer.innerHTML = '';

    if (exercise.type === 'vocabulary') {
        createVocabExercise(exercise);
    } else if (exercise.type === 'grammar') {
        createGrammarExercise(exercise);
    }
}

function createVocabExercise(exercise) {
    const container = document.getElementById('exercise-container');
    exercise.words.forEach((word, index) => {
        const card = document.createElement('div');
        card.className = 'card mb-3';
        card.innerHTML = `
            <div class="card-body">
                <h5 class="card-title">${word}</h5>
                <input type="text" class="form-control" placeholder="Enter translation">
                <button class="btn btn-primary mt-2" onclick="checkVocabAnswer(${index})">Check</button>
            </div>
        `;
        container.appendChild(card);
    });
}

function createGrammarExercise(exercise) {
    const container = document.getElementById('exercise-container');
    exercise.sentences.forEach((sentence, index) => {
        const card = document.createElement('div');
        card.className = 'card mb-3';
        card.innerHTML = `
            <div class="card-body">
                <h5 class="card-title">${sentence}</h5>
                <input type="text" class="form-control" placeholder="Enter translation">
                <button class="btn btn-primary mt-2" onclick="checkGrammarAnswer(${index})">Check</button>
            </div>
        `;
        container.appendChild(card);
    });
}

async function saveProgress() {
    try {
        const response = await fetch('/api/save-progress', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                exercise_id: exercises[currentExercise].id,
                score: score
            }),
        });

        if (!response.ok) {
            throw new Error('Failed to save progress');
        }
    } catch (error) {
        console.error('Progress save error:', error);
    }
}

document.addEventListener('DOMContentLoaded', loadExercise);
// Exercise data
const exercises = [
    {
        type: 'vocabulary',
        question: 'What is the English word for "casa"?',
        options: ['House', 'Car', 'Book', 'Dog'],
        answer: 'House'
    },
    {
        type: 'vocabulary',
        question: 'What is the English word for "libro"?',
        options: ['Pencil', 'Book', 'Table', 'Computer'],
        answer: 'Book'
    },
    {
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
            <button class="btn btn-success mt-3" onclick="checkVocabAnswer()">Check Answer</button>
        `;
    }
    
    exerciseContainer.innerHTML = exerciseHTML;
}

// Function to check vocabulary exercise answer
function checkVocabAnswer() {
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

// Function to move to the previous exercise
function previousExercise() {
    if (currentExerciseIndex > 0) {
        currentExerciseIndex--;
        displayExercise();
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
    
    // Hide navigation buttons
    document.getElementById('prev-btn').style.display = 'none';
    document.getElementById('next-btn').style.display = 'none';
}

// Function to restart exercises
function restartExercises() {
    currentExerciseIndex = 0;
    score = 0;
    
    // Show navigation buttons
    document.getElementById('prev-btn').style.display = 'block';
    document.getElementById('next-btn').style.display = 'block';
    
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
                exercise_id: `vocab_${currentExerciseIndex}`,
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
