import {
  auth,
  browserLocalPersistence,
  collection,
  createUserWithEmailAndPassword,
  db,
  doc,
  firebaseConfigured,
  sendPasswordResetEmail,
  serverTimestamp,
  setDoc,
  setPersistence,
  signInWithEmailAndPassword,
  updateProfile
} from "./firebase-client.js";

const loginForm = document.getElementById("login-form");
const signupForm = document.getElementById("signup-form");
const loginPanel = document.getElementById("login-panel");
const signupPanel = document.getElementById("signup-panel");
const notice = document.getElementById("auth-notice");
const errorMessage = document.getElementById("auth-error");
const loginFields = document.getElementById("login-fields");
const signupFields = document.getElementById("signup-fields");
const signupButton = document.getElementById("signup-submit");
const resetButton = document.getElementById("reset-password");

function showError(message) {
  errorMessage.textContent = message;
  errorMessage.hidden = false;
}

function showNotice(message) {
  notice.textContent = message;
  notice.hidden = !message;
}

function clearMessages() {
  errorMessage.textContent = "";
  errorMessage.hidden = true;
  showNotice("");
}

function displayFirebaseError(error, operation) {
  const messages = {
    "auth/invalid-email": "Enter a valid email address.",
    "auth/invalid-credential": "The email or password is incorrect.",
    "auth/user-not-found": "The email or password is incorrect.",
    "auth/wrong-password": "The email or password is incorrect.",
    "auth/email-already-in-use": "An account already uses this email. Try logging in instead.",
    "auth/weak-password": "Choose a stronger password with at least 8 characters.",
    "auth/too-many-requests": "There have been too many attempts. Wait a little and try again.",
    "auth/network-request-failed": "A network error interrupted the request. Check your connection and try again.",
    "auth/operation-not-allowed": "Email and password sign-in is not enabled for this Firebase project.",
    "auth/unauthorized-domain": "This website domain is not authorized in your Firebase Authentication settings."
  };
  showError(messages[error.code] || `Unable to ${operation}. Check your Firebase settings and connection, then try again.`);
}

function setBusy(form, busy) {
  const fields = form.querySelector("fieldset");
  const button = form.querySelector('button[type="submit"]');
  fields.disabled = busy;
  button.textContent = busy ? "Please wait..." : (form === loginForm ? "Log in" : "Create account");
}

function waitForProfileSave(profileWrite, timeoutMs) {
  let timeoutId;
  const timeout = new Promise((_, reject) => {
    timeoutId = window.setTimeout(() => reject(new Error("profile-save-timeout")), timeoutMs);
  });
  return Promise.race([profileWrite, timeout]).finally(() => window.clearTimeout(timeoutId));
}

function isValidNextPage(path) {
  return new Set(["share-food.html", "find-food.html", "volunteer.html", "account.html"]).has(path);
}

function finishSignIn() {
  const requestedPage = new URLSearchParams(window.location.search).get("next");
  window.location.replace(isValidNextPage(requestedPage) ? requestedPage : "index.html");
}

if (!firebaseConfigured || !auth || !db) {
  showNotice("Account services are not configured. Contact the site administrator.");
} else {
  try {
    await setPersistence(auth, browserLocalPersistence);
    loginFields.disabled = false;
    signupFields.disabled = false;
    showNotice("");

    document.getElementById("show-signup").addEventListener("click", () => {
      clearMessages();
      loginPanel.hidden = true;
      signupPanel.hidden = false;
    });

    document.getElementById("show-login").addEventListener("click", () => {
      clearMessages();
      signupPanel.hidden = true;
      loginPanel.hidden = false;
    });

    loginForm.addEventListener("submit", async event => {
      event.preventDefault();
      clearMessages();
      setBusy(loginForm, true);
      try {
        await signInWithEmailAndPassword(
          auth,
          document.getElementById("login-email").value.trim(),
          document.getElementById("login-password").value
        );
        finishSignIn();
      } catch (error) {
        displayFirebaseError(error, "sign in");
        setBusy(loginForm, false);
      }
    });

    signupForm.addEventListener("submit", async event => {
      event.preventDefault();
      clearMessages();
      setBusy(signupForm, true);
      const displayName = document.getElementById("signup-name").value.trim();
      const email = document.getElementById("signup-email").value.trim();
      const password = document.getElementById("signup-password").value;
      const requestedRole = document.getElementById("signup-role").value;
      let accountCreated = false;

      try {
        showNotice("Creating your account...");
        const credential = await createUserWithEmailAndPassword(auth, email, password);
        accountCreated = true;
        await updateProfile(credential.user, { displayName });
        showNotice("Saving your FoodBridge profile...");
        const profileWrite = setDoc(doc(collection(db, "profiles"), credential.user.uid), {
          displayName,
          requestedRole,
          role: "pending",
          approvalStatus: "pending",
          createdAt: serverTimestamp()
        });
        try {
          await waitForProfileSave(profileWrite, 20000);
        } catch (error) {
          if (error.message === "profile-save-timeout") {
            profileWrite.then(() => {
              showNotice("Your profile was saved. Opening FoodBridge...");
              finishSignIn();
            }, profileError => {
              console.error("Could not save the new FoodBridge profile.", profileError);
            });
          }
          throw error;
        }
        finishSignIn();
      } catch (error) {
        if (accountCreated) {
          console.error("Could not complete the new FoodBridge profile.", error);
          showError(error.message === "profile-save-timeout"
            ? "Your sign-in was created, but setting up your FoodBridge profile is taking too long. Do not create another account. Check your connection and Firestore rules, then try logging in again."
            : "Your sign-in was created, but FoodBridge could not finish setting up your profile. Do not create another account. Check that Firestore is enabled and the latest firestore.rules are deployed, then try logging in again.");
        } else {
          displayFirebaseError(error, "create your account");
        }
      } finally {
        signupFields.disabled = false;
        signupButton.textContent = "Create account";
      }
    });

    resetButton.addEventListener("click", async () => {
      clearMessages();
      const email = document.getElementById("login-email").value.trim();
      if (!email) {
        showError("Enter your email address first, then choose Forgot password.");
        document.getElementById("login-email").focus();
        return;
      }
      resetButton.disabled = true;
      try {
        await sendPasswordResetEmail(auth, email);
        showNotice("If an account exists for that email, Firebase has sent a password reset message.");
      } catch (error) {
        displayFirebaseError(error, "send the password reset");
      } finally {
        resetButton.disabled = false;
      }
    });

  } catch (error) {
    showError("Firebase could not be initialized. Check the Firebase web app settings and try again.");
    console.error("Firebase Authentication initialization failed.", error);
  }
}
