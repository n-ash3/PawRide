import SwiftUI

struct OTPVerifyView: View {
    @EnvironmentObject private var authStore: AuthStore
    let phoneNumber: String
    let profileName: String
    let requestedDriverRole: Bool
    @Binding var otpCode: String
    let onBack: () -> Void

    var body: some View {
        VStack(spacing: 14) {
            Text("Enter OTP sent to \(phoneNumber)")
                .font(.headline)
            TextField("6-digit OTP", text: $otpCode)
                .keyboardType(.numberPad)
                .textFieldStyle(.roundedBorder)

            HStack {
                Button("Back", action: onBack)
                    .buttonStyle(.bordered)

                Button {
                    Task {
                        var roles: [AppRole] = []
                        if requestedDriverRole {
                            roles.append(.driver)
                        }
                        _ = await authStore.verifyOTP(
                            phoneNumber: phoneNumber,
                            code: otpCode,
                            name: profileName,
                            requestedRoles: roles
                        )
                    }
                } label: {
                    if authStore.isLoading {
                        ProgressView()
                    } else {
                        Text("Verify & Continue")
                    }
                }
                .buttonStyle(.borderedProminent)
                .disabled(otpCode.count < 4 || authStore.isLoading)
            }

            if let errorMessage = authStore.errorMessage {
                Text(errorMessage)
                    .font(.footnote)
                    .foregroundStyle(.red)
            }
        }
        .padding()
        .background(PawRideTheme.card, in: RoundedRectangle(cornerRadius: 16))
    }
}
