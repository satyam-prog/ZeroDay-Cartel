import {
  Timestamp,
  auth,
  collection,
  db,
  doc,
  getDoc,
  getDocs,
  limit,
  query,
  runTransaction,
  serverTimestamp,
  updateDoc,
  where
} from "./firebase-client.js";
import { requireRole, setPageMessage } from "./page-auth.js";

const form = document.getElementById("listing-form");
const list = document.getElementById("listing-list");
const formMessage = document.getElementById("form-message");
const submitButton = document.getElementById("listing-submit");
let currentUser;
let currentProfile;

function message(element, text, type = "info") {
  element.textContent = text;
  element.className = `fb-page-status fb-page-status-${type}`;
  element.hidden = !text;
}

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function formatDate(value) {
  return value?.toDate ? value.toDate().toLocaleString("en-IN") : "Not available";
}

async function loadListings() {
  list.replaceChildren(makeElement("p", "", "Loading your listings..."));
  try {
    const [listingSnapshot, requestSnapshot] = await Promise.all([
      getDocs(query(collection(db, "listings"), where("ownerUid", "==", currentUser.uid), limit(50))),
      getDocs(query(collection(db, "requests"), where("donorUid", "==", currentUser.uid), limit(100)))
    ]);
    const requestsByListing = new Map();
    requestSnapshot.forEach(requestDoc => {
      const request = { id: requestDoc.id, ...requestDoc.data() };
      const requests = requestsByListing.get(request.listingId) || [];
      requests.push(request);
      requestsByListing.set(request.listingId, requests);
    });

    const listings = listingSnapshot.docs
      .map(item => ({ id: item.id, ...item.data() }))
      .sort((a, b) => (b.createdAt?.toMillis?.() || 0) - (a.createdAt?.toMillis?.() || 0));
    list.replaceChildren();
    if (!listings.length) {
      list.append(makeElement("p", "fb-empty-state", "You have not posted any food listings yet."));
      return;
    }

    listings.forEach(item => {
      const card = makeElement("article", "fb-record-card");
      const heading = makeElement("div", "fb-record-heading");
      heading.append(
        makeElement("h3", "", item.foodName),
        makeElement("span", `fb-record-status fb-status-${item.status}`, item.status)
      );
      card.append(heading);
      card.append(makeElement("p", "", `${item.quantity} ${item.unit} · ${item.pickupArea}`));
      card.append(makeElement("p", "fb-record-meta", `Pickup by ${formatDate(item.pickupBy)} · Use by ${formatDate(item.expiresAt)}`));

      if (item.status === "available") {
        const cancel = makeElement("button", "fb-inline-action", "Close listing");
        cancel.type = "button";
        cancel.addEventListener("click", async () => {
          cancel.disabled = true;
          try {
            await updateDoc(doc(db, "listings", item.id), { status: "cancelled" });
            await loadListings();
          } catch (error) {
            console.error("Could not close the food listing.", error);
            cancel.disabled = false;
            message(formMessage, "Could not close this listing. Refresh and try again.", "error");
          }
        });
        card.append(cancel);
      }

      const requests = requestsByListing.get(item.id) || [];
      if (requests.length) {
        const requestHeading = makeElement("h4", "fb-record-subheading", `Requests (${requests.length})`);
        card.append(requestHeading);
        requests.forEach(request => {
          const requestCard = makeElement("div", "fb-request-card");
          requestCard.append(makeElement("strong", "", request.requesterName));
          requestCard.append(makeElement("p", "", request.message));
          requestCard.append(makeElement("span", "fb-record-meta", `Request status: ${request.status}`));
          if (request.status === "pending" && item.status === "available") {
            const actions = makeElement("div", "fb-record-actions");
            const accept = makeElement("button", "btn-primary", "Accept and arrange delivery");
            const reject = makeElement("button", "btn-secondary", "Decline");
            accept.type = "button";
            reject.type = "button";
            accept.addEventListener("click", () => acceptRequest(item, request, accept));
            reject.addEventListener("click", () => rejectRequest(request, reject));
            actions.append(accept, reject);
            requestCard.append(actions);
          }
          card.append(requestCard);
        });
      } else if (item.status === "available") {
        card.append(makeElement("p", "fb-record-meta", "No kitchen requests yet."));
      }
      list.append(card);
    });
  } catch (error) {
    console.error("Could not load the donor's food listings.", error);
    list.replaceChildren(makeElement("p", "fb-page-status fb-page-status-error", "Could not load your listings. Check your connection and refresh."));
  }
}

async function acceptRequest(listing, request, button) {
  button.disabled = true;
  try {
    const taskRef = doc(collection(db, "deliveryTasks"));
    const listingRef = doc(db, "listings", listing.id);
    const requestRef = doc(db, "requests", request.id);

    await runTransaction(db, async transaction => {
      const [listingSnapshot, requestSnapshot] = await Promise.all([
        transaction.get(listingRef),
        transaction.get(requestRef)
      ]);
      if (!listingSnapshot.exists() || !requestSnapshot.exists()
          || listingSnapshot.data().status !== "available"
          || requestSnapshot.data().status !== "pending") {
        throw new Error("This listing or request is no longer available.");
      }

      const currentListing = listingSnapshot.data();
      transaction.update(listingRef, {
        status: "matched",
        matchedKitchenUid: request.requesterUid,
        acceptedRequestId: request.id,
        deliveryTaskId: taskRef.id,
        matchedAt: serverTimestamp()
      });
      transaction.update(requestRef, {
        status: "accepted",
        updatedAt: serverTimestamp()
      });
      transaction.set(taskRef, {
        listingId: listing.id,
        requestId: request.id,
        donorUid: currentUser.uid,
        kitchenUid: request.requesterUid,
        volunteerUid: null,
        status: "open",
        foodName: currentListing.foodName,
        quantity: currentListing.quantity,
        unit: currentListing.unit,
        pickupBy: currentListing.pickupBy,
        pickupArea: currentListing.pickupArea,
        createdAt: serverTimestamp()
      });
    });
    message(formMessage, "Request accepted. An approved volunteer can now claim the delivery.");
    await loadListings();
  } catch (error) {
    console.error("Could not accept the community kitchen request.", error);
    message(formMessage, "Could not accept this request. It may have changed; refresh and try again.", "error");
    button.disabled = false;
  }
}

async function rejectRequest(request, button) {
  button.disabled = true;
  try {
    await updateDoc(doc(db, "requests", request.id), {
      status: "rejected",
      updatedAt: serverTimestamp()
    });
    await loadListings();
  } catch (error) {
    console.error("Could not decline the community kitchen request.", error);
    message(formMessage, "Could not decline this request. Refresh and try again.", "error");
    button.disabled = false;
  }
}

requireRole(["donor"], ({ user, profile }) => {
  currentUser = user;
  currentProfile = profile;
  loadListings();
});

form.addEventListener("submit", async event => {
  event.preventDefault();
  message(formMessage, "");
  if (!currentUser || !currentProfile) return;

  const pickupByDate = new Date(document.getElementById("pickup-by").value);
  const expiresAtDate = new Date(document.getElementById("expires-at").value);
  if (!Number.isFinite(pickupByDate.getTime()) || pickupByDate <= new Date()) {
    message(formMessage, "Choose a future pickup deadline.", "error");
    return;
  }
  if (!Number.isFinite(expiresAtDate.getTime()) || expiresAtDate < pickupByDate) {
    message(formMessage, "The use-by time must be after the pickup deadline.", "error");
    return;
  }

  submitButton.disabled = true;
  try {
    const listingRef = doc(collection(db, "listings"));
    const privateRef = doc(db, "listingPrivate", listingRef.id);
    await runTransaction(db, async transaction => {
      transaction.set(listingRef, {
        ownerUid: currentUser.uid,
        donorName: currentProfile.displayName,
        foodName: document.getElementById("food-name").value.trim(),
        category: document.getElementById("food-category").value,
        quantity: Number(document.getElementById("food-quantity").value),
        unit: document.getElementById("food-unit").value,
        pickupArea: document.getElementById("pickup-area").value.trim(),
        serviceArea: "Gurugram, Haryana",
        pickupBy: Timestamp.fromDate(pickupByDate),
        expiresAt: Timestamp.fromDate(expiresAtDate),
        notes: document.getElementById("food-notes").value.trim(),
        foodSafetyConfirmed: document.getElementById("food-safety-confirmed").checked,
        status: "available",
        createdAt: serverTimestamp()
      });
      transaction.set(privateRef, {
        ownerUid: currentUser.uid,
        pickupAddress: document.getElementById("pickup-address").value.trim(),
        contactPhone: document.getElementById("contact-phone").value.trim()
      });
    });
    form.reset();
    message(formMessage, "Your food listing is now available to approved community kitchens.");
    await loadListings();
  } catch (error) {
    console.error("Could not publish the food listing.", error);
    message(formMessage, "Could not publish your listing. Check the form and your Firebase connection, then try again.", "error");
  } finally {
    submitButton.disabled = false;
  }
});

document.getElementById("refresh-listings").addEventListener("click", loadListings);
