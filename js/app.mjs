import { createClient } from "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.118.0/+esm";
import { calculateForecast } from "./forecast.mjs";
import { SUPABASE_PUBLISHABLE_KEY, SUPABASE_URL } from "./supabase-config.js";

const supabase = createClient(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY);
const views = {
  login: document.querySelector("#login-view"),
  forecast: document.querySelector("#forecast-view"),
  result: document.querySelector("#result-view"),
  loading: document.querySelector("#loading-view"),
};
const loginForm = document.querySelector("#login-form");
const loginSubmit = document.querySelector("#login-submit");
const loginError = document.querySelector("#login-error");
const loginErrorMessage = document.querySelector("#login-error-message");
const forecastForm = document.querySelector("#forecast-form");
const forecastSubmit = document.querySelector("#forecast-submit");
const forecastError = document.querySelector("#forecast-error");
const forecastErrorMessage = document.querySelector("#forecast-error-message");
const signOutButton = document.querySelector("#sign-out");
const accountEmail = document.querySelector("#account-email");
const breadcrumb = document.querySelector("#breadcrumb-current");
const accountError = document.querySelector("#account-error");
const accountErrorMessage = document.querySelector("#account-error-message");

function showView(name) {
  for (const [viewName, element] of Object.entries(views)) {
    element.hidden = viewName !== name;
  }
  breadcrumb.textContent = name === "login" ? "Sign in" : "Performance forecast";
  signOutButton.hidden = name === "login" || name === "loading";
}

function setError(element, messageElement, message) {
  messageElement.textContent = message;
  element.hidden = false;
}

function showResult(inputs, forecast) {
  document.querySelector("#result-status").textContent = `${forecast.status}, ${inputs.enrollmentNo}.`;
  document.querySelector("#result-score").textContent = String(forecast.score);
  document.querySelector("#result-headline").textContent = forecast.headline;
  document.querySelector("#result-message").textContent = forecast.message;
  document.querySelector("#result-pill-text").textContent = forecast.passed
    ? "On a positive path"
    : "A chance to reset and refocus";
  const ring = document.querySelector("#score-ring");
  ring.style.setProperty("--score", String(forecast.score));
  ring.classList.toggle("ring-warm", !forecast.passed);
  const pill = document.querySelector("#result-pill");
  pill.classList.toggle("positive", forecast.passed);
  pill.classList.toggle("supportive", !forecast.passed);
  const shareText = `My projected final score is ${forecast.score}/100 (${forecast.status}).`;
  document.querySelector("#share-link").href =
    `https://wa.me/?text=${encodeURIComponent(shareText)}`;
  showView("result");
  window.scrollTo({ top: 0, behavior: "smooth" });
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.hidden = true;
  loginSubmit.disabled = true;
  const formData = new FormData(loginForm);
  const { error } = await supabase.auth.signInWithPassword({
    email: String(formData.get("email")).trim(),
    password: String(formData.get("password")),
  });
  loginSubmit.disabled = false;
  if (error) {
    setError(loginError, loginErrorMessage, "Check your email and password, then try again.");
  }
});

forecastForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  forecastError.hidden = true;
  forecastSubmit.disabled = true;
  const formData = new FormData(forecastForm);
  const inputs = {
    enrollmentNo: String(formData.get("enrollment_no")).trim(),
    studyHours: Number(formData.get("study_hours")),
    percentage: Number(formData.get("percentage")),
    attendance: Number(formData.get("attendance")),
  };
  if (
    !inputs.enrollmentNo
    || inputs.enrollmentNo.length > 32
    || formData.get("study_hours") === ""
    || formData.get("percentage") === ""
    || formData.get("attendance") === ""
    || !Number.isFinite(inputs.studyHours)
    || !Number.isFinite(inputs.percentage)
    || !Number.isFinite(inputs.attendance)
    || inputs.studyHours < 0 || inputs.studyHours > 24
    || inputs.percentage < 0 || inputs.percentage > 100
    || inputs.attendance < 0 || inputs.attendance > 100
  ) {
    setError(forecastError, forecastErrorMessage, "Enter a valid enrollment number and values within the displayed ranges.");
    forecastSubmit.disabled = false;
    return;
  }

  const { data: { user }, error: userError } = await supabase.auth.getUser();
  if (userError || !user) {
    forecastSubmit.disabled = false;
    await supabase.auth.signOut();
    setError(loginError, loginErrorMessage, "Your session expired. Sign in again before submitting student details.");
    return;
  }

  const forecast = calculateForecast(inputs);
  const { error } = await supabase.from("student_predictions").insert({
    user_id: user.id,
    enrollment_no: inputs.enrollmentNo,
    study_hours: inputs.studyHours,
    percentage: inputs.percentage,
    attendance: inputs.attendance,
    predicted_percentage: forecast.score,
  });
  forecastSubmit.disabled = false;
  if (error) {
    setError(
      forecastError,
      forecastErrorMessage,
      `Supabase couldn't save this submission: ${error.message}. Confirm you ran supabase/schema.sql and check the table's Row Level Security policies, then try again.`,
    );
    return;
  }

  forecastForm.reset();
  showResult(inputs, forecast);
});

document.querySelector("#new-forecast").addEventListener("click", () => {
  forecastError.hidden = true;
  showView("forecast");
  window.scrollTo({ top: 0, behavior: "smooth" });
});

signOutButton.addEventListener("click", async () => {
  signOutButton.disabled = true;
  const { error } = await supabase.auth.signOut();
  signOutButton.disabled = false;
  if (error) {
    setError(accountError, accountErrorMessage, "Supabase couldn't sign you out. Check your connection and try again.");
  }
});

supabase.auth.onAuthStateChange((_event, session) => {
  if (session?.user) {
    accountEmail.textContent = session.user.email ?? "";
    if (views.login.hidden === false) {
      showView("forecast");
    }
  } else {
    accountEmail.textContent = "";
    loginForm.reset();
    showView("login");
  }
});

const { data: { session }, error: sessionError } = await supabase.auth.getSession();
if (sessionError) {
  setError(loginError, loginErrorMessage, "Couldn't connect to Supabase. Check the project configuration and refresh.");
}
if (session?.user) {
  accountEmail.textContent = session.user.email ?? "";
  showView("forecast");
} else {
  showView("login");
}
