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
    const displayName = profile?.displayName || user.displayName || user.email || "My account";
    const initials = displayName
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map(part => part[0])
      .join("")
      .toUpperCase() || "U";
    const summary = makeElement("summary", "fb-account-summary");
    summary.setAttribute("aria-label", `Open account menu for ${displayName}`);
    summary.title = displayName;
    const avatar = makeElement("span", "fb-account-avatar", initials);
    avatar.setAttribute("aria-hidden", "true");
    if (user.photoURL) {
      try {
        const photoUrl = new URL(user.photoURL);
        if (photoUrl.protocol === "https:") {
          const image = makeElement("img", "fb-account-avatar-image");
          image.src = photoUrl.href;
          image.alt = "";
          image.addEventListener("error", () => image.remove(), { once: true });
          avatar.append(image);
        }
      } catch {
        console.error("Could not display the signed-in user's profile photo URL.");
      }
    }
    summary.append(avatar);
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

      renderSignedIn(user, null);
      try {
        const profileSnapshot = await getDoc(doc(db, "profiles", user.uid));
        if (auth.currentUser?.uid === user.uid) {
          renderSignedIn(user, profileSnapshot.exists() ? profileSnapshot.data() : null);
        }
      } catch (error) {
        console.error("Could not load the signed-in FoodBridge profile.", error);
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
