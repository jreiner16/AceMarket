// StorageUtils -- helper class for loading things from firebase storage
import { ref, uploadBytes, getDownloadURL, getBytes } from 'firebase/storage'
import { storage } from './firebase'

/**
 * Upload a file to Firebase Storage.
 * @param {string} path - Path in storage (e.g. "users/{uid}/portfolio.json")
 * @param {Blob|File|ArrayBuffer} data - File data
 * @returns {Promise<string>} Download URL
 */
export async function uploadFile(path, data) {
  const storageRef = ref(storage, path)
  const snapshot = await uploadBytes(storageRef, data)
  return getDownloadURL(snapshot.ref)
}

/**
 * Download file content as text (e.g. for JSON).
 * @param {string} path - Path in storage
 * @returns {Promise<string>} File content as string
 */
export async function downloadFileAsText(path) {
  const storageRef = ref(storage, path)
  const bytes = await getBytes(storageRef)
  return new TextDecoder().decode(bytes)
}
