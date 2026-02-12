import SwiftUI

struct PhoneEntryView: View {
    @EnvironmentObject private var authStore: AuthStore
    @Binding var phoneNumber: String
    @Binding var profileName: String
    @Binding var requestedDriverRole: Bool
    let onContinue: () -> Void

    var body: some View {
        VStack(spacing: 14) {
            TextField("+1 555 000 0000", text: $phoneNumber)
                .keyboardType(.phonePad)
                .textFieldStyle(.roundedBorder)
            TextField("Your name", text: $profileName)
                .textFieldStyle(.roundedBorder)
            Toggle("I also want Driver access", isOn: $requestedDriverRole)

            Button {
                Task {
                    await authStore.requestOTP(phoneNumber: phoneNumber)
                    if authStore.errorMessage == nil {
                        onContinue()
                    }
                }
            } label: {
                if authStore.isLoading {
                    ProgressView()
                } else {
                    Text("Send OTP")
                        .frame(maxWidth: .infinity)
                }
            }
            .buttonStyle(.borderedProminent)
            .disabled(phoneNumber.isEmpty || authStore.isLoading)

            if let devCode = authStore.lastDevCode {
                Text("Dev OTP: \(devCode)")
                    .font(.footnote.monospaced())
                    .foregroundStyle(.secondary)
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
