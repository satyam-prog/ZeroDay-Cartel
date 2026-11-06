import {
  auth,
  db,
  doc,
  firebaseConfigured,
  getDoc,
  onAuthStateChanged,
  setPersistence,
  browserLocalPersistence,
  signOut
} from "./firebase-client.js";

const slots = [
  document.getElementById("desktop-account-nav"),
  document.getElementById("mobile-account-nav")
].filter(Boolean);

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function renderSignedOut() {
  slots.forEach(slot => {
    slot.replaceChildren();
    const link = makeElement("a", "btn-secondary", "Log in");
    link.href = "login.html";
    slot.append(link);
  });
}

function renderSignedIn(user, profile) {
  slots.forEach(slot => {
    slot.replaceChildren();
    const details = makeElement("details", "fb-account-menu");
    const summary = makeElement("summary", "fb-account-summary", profile?.displayName || user.email || "My account");
    const menu = makeElement("div", "fb-account-dropdown");
    const accountLink = makeElement("a", "", "My account");
    accountLink.href = "account.html";
    const roleLabel = profile?.role === "pending"
      ? "Account under review"
      : (profile?.role || "FoodBridge member");
    const status = makeElement("span", "fb-account-role", roleLabel);
    const signOutButton = makeElement("button", "", "Sign out");
    signOutButton.type = "button";
    signOutButton.addEventListener("click", async () => {
      signOutButton.disabled = true;
      try {
        await signOut(auth);
        window.location.assign("index.html");
      } catch (error) {
        signOutButton.disabled = false;
        console.error("Could not sign out of Firebase Authentication.", error);
        status.textContent = "Sign out failed. Please try again.";
      }
    });
    menu.append(accountLink, status, signOutButton);
    details.append(summary, menu);
    slot.append(details);
  });
}

if (!firebaseConfigured || !auth || !db) {
  renderSignedOut();
} else {
  try {
    await setPersistence(auth, browserLocalPersistence);
    onAuthStateChanged(auth, async user => {
      if (!user) {
        renderSignedOut();
        return;
      }

      try {
        const profileSnapshot = await getDoc(doc(db, "profiles", user.uid));
        renderSignedIn(user, profileSnapshot.exists() ? profileSnapshot.data() : null);
      } catch (error) {
        console.error("Could not load the signed-in FoodBridge profile.", error);
        renderSignedIn(user, null);
      }
    }, error => {
      console.error("Could not observe Firebase Authentication state.", error);
      renderSignedOut();
    });
  } catch (error) {
    console.error("Could not initialize the FoodBridge account menu.", error);
    renderSignedOut();
  }
}
