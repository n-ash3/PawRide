# PawRide iOS App Source (Phases 3-5)

This folder contains a **single-app SwiftUI architecture** for PawRide with role switching:

- Dog Parent mode
- Driver mode
- Admin mode

## Included

- Phone + OTP auth flow
- Role picker for multi-role users
- Role switching from settings
- Parent tab shell + ride request/tracking placeholders
- Driver tab shell + online toggle + onboarding hooks
- Admin tab shell + dashboard/rides/users/analytics placeholders
- Backend API integration points (request OTP, verify OTP, switch role, ride request, driver online)
- Realtime websocket service placeholder for ride updates

## How to use in Xcode

1. Create a new iOS App project in Xcode (`PawRide`).
2. Copy all files from this folder into the Xcode project.
3. Set deployment target to iOS 17+.
4. Ensure `Info.plist` includes:
   - `NSLocationWhenInUseUsageDescription`
   - `NSCameraUsageDescription`
   - `NSMicrophoneUsageDescription`
   - `NSPhotoLibraryAddUsageDescription`
5. Update `APIClient.baseURL` to your deployed backend URL.

## Note

This is source-first scaffolding intended to accelerate development and match the backend flows in this repo.
