import {
  collection,
  db,
  doc,
  getDoc,
  getDocs,
  limit,
  query,
  runTransaction,
  serverTimestamp,
  where
} from "./firebase-client.js";
import { requireRole } from "./page-auth.js";

const taskList = document.getElementById("task-list");
const claimedList = document.getElementById("claimed-list");
let currentUser;

function makeElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text) element.textContent = text;
  return element;
}

function formatDate(value) {
  return value?.toDate ? value.toDate().toLocaleString("en-IN") : "Not available";
}

async function renderTask(container, task, isClaimed) {
  const card = makeElement("article", "fb-record-card");
  const heading = makeElement("div", "fb-record-heading");
  heading.append(
    makeElement("h3", "", task.foodName),
    makeElement("span", `fb-record-status fb-status-${task.status}`, task.status)
  );
  card.append(heading);
  card.append(makeElement("p", "", `${task.quantity} ${task.unit} · ${task.pickupArea}`));
  card.append(makeElement("p", "fb-record-meta", `Pickup by ${formatDate(task.pickupBy)}`));

  if (isClaimed) {
    if (task.status === "claimed") {
      const privateSnapshot = await getDoc(doc(db, "listingPrivate", task.listingId));
      if (privateSnapshot.exists()) {
        const details = privateSnapshot.data();
        card.append(makeElement("p", "fb-record-subheading", "Pickup contact"));
        card.append(makeElement("p", "", details.pickupAddress));
        card.append(makeElement("p", "", `Donor phone: ${details.contactPhone}`));
      }
      const complete = makeElement("button", "btn-primary", "Mark delivery complete");
      complete.type = "button";
      complete.addEventListener("click", async () => {
        complete.disabled = true;
        try {
          await runTransaction(db, async transaction => {
            const taskRef = doc(db, "deliveryTasks", task.id);
            const snapshot = await transaction.get(taskRef);
            if (!snapshot.exists() || snapshot.data().status !== "claimed"
                || snapshot.data().volunteerUid !== currentUser.uid) {
              throw new Error("This delivery task is no longer assigned to you.");
            }
            transaction.update(taskRef, {
              status: "delivered",
              completedAt: serverTimestamp()
            });
          });
          await loadTasks();
        } catch (error) {
          console.error("Could not complete the delivery task.", error);
          complete.disabled = false;
          card.append(makeElement("p", "fb-page-status fb-page-status-error", "Could not mark this delivery complete. Refresh and try again."));
        }
      });
      card.append(complete);
    } else {
      card.append(makeElement("p", "fb-record-meta", `Delivery marked ${formatDate(task.completedAt)}.`));
    }
  } else {
    const button = makeElement("button", "btn-primary", "Claim delivery");
    button.type = "button";
    button.addEventListener("click", async () => {
      button.disabled = true;
      try {
        await runTransaction(db, async transaction => {
          const taskRef = doc(db, "deliveryTasks", task.id);
          const snapshot = await transaction.get(taskRef);
          if (!snapshot.exists() || snapshot.data().status !== "open") {
            throw new Error("This delivery task has already been claimed.");
          }
          transaction.update(taskRef, {
            status: "claimed",
            volunteerUid: currentUser.uid,
            claimedAt: serverTimestamp()
          });
        });
        await loadTasks();
      } catch (error) {
        console.error("Could not claim the delivery task.", error);
        button.disabled = false;
        card.append(makeElement("p", "fb-page-status fb-page-status-error", "This task could not be claimed. It may have been taken by another volunteer."));
      }
    });
    card.append(button);
  }
  container.append(card);
}

async function loadTasks() {
  taskList.replaceChildren(makeElement("p", "", "Loading open delivery tasks..."));
  claimedList.replaceChildren(makeElement("p", "", "Loading your claimed tasks..."));
  try {
    const [openSnapshot, claimedSnapshot] = await Promise.all([
      getDocs(query(collection(db, "deliveryTasks"), where("status", "==", "open"), limit(50))),
      getDocs(query(collection(db, "deliveryTasks"), where("volunteerUid", "==", currentUser.uid), limit(50)))
    ]);
    const openTasks = openSnapshot.docs.map(item => ({ id: item.id, ...item.data() }));
    const claimedTasks = claimedSnapshot.docs.map(item => ({ id: item.id, ...item.data() }));
    taskList.replaceChildren();
    claimedList.replaceChildren();
    if (!openTasks.length) taskList.append(makeElement("p", "fb-empty-state", "There are no open delivery tasks right now."));
    for (const task of openTasks) await renderTask(taskList, task, false);
    if (!claimedTasks.length) claimedList.append(makeElement("p", "fb-empty-state", "You have not claimed a delivery task."));
    for (const task of claimedTasks) await renderTask(claimedList, task, true);
  } catch (error) {
    console.error("Could not load volunteer delivery tasks.", error);
    taskList.replaceChildren(makeElement("p", "fb-page-status fb-page-status-error", "Could not load delivery tasks. Check your connection and refresh."));
    claimedList.replaceChildren(makeElement("p", "fb-page-status fb-page-status-error", "Could not load your claimed tasks."));
  }
}

requireRole(["volunteer"], ({ user }) => {
  currentUser = user;
  loadTasks();
});

document.getElementById("refresh-tasks").addEventListener("click", loadTasks);
