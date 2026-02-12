import SwiftUI

struct AuthFlowView: View {
    @State private var phoneNumber = ""
    @State private var profileName = ""
    @State private var otpCode = ""
    @State private var requestedDriverRole = false
    @State private var step: Step = .phone

    enum Step {
        case phone
        case otp
    }

    var body: some View {
        ZStack {
            PawRideTheme.background.ignoresSafeArea()
            VStack(spacing: 20) {
                Text("PawRide")
                    .font(.largeTitle.bold())
                    .foregroundStyle(PawRideTheme.primary)
                Text("Safe rides, happy pups.")
                    .foregroundStyle(.secondary)

                if step == .phone {
                    PhoneEntryView(
                        phoneNumber: $phoneNumber,
                        profileName: $profileName,
                        requestedDriverRole: $requestedDriverRole,
                        onContinue: { step = .otp }
                    )
                } else {
                    OTPVerifyView(
                        phoneNumber: phoneNumber,
                        profileName: profileName,
                        requestedDriverRole: requestedDriverRole,
                        otpCode: $otpCode,
                        onBack: { step = .phone }
                    )
                }
            }
            .padding()
        }
    }
}
