import SwiftUI

struct ParentSettingsView: View {
    @EnvironmentObject private var authStore: AuthStore
    @State private var onboardingMessage: String?

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                List {
                    Section("Driver Onboarding") {
                        Button("Become a Driver") {
                            Task { await becomeDriver() }
                        }
                        if let onboardingMessage {
                            Text(onboardingMessage)
                                .font(.footnote)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                RoleSettingsPanel()
                    .frame(maxHeight: 360)
            }
            .background(PawRideTheme.background)
            .navigationTitle("Settings")
        }
    }

    private func becomeDriver() async {
        guard let token = authStore.accessToken else { return }
        do {
            try await APIClient.shared.becomeDriver(accessToken: token)
            onboardingMessage = "Driver role requested. Complete profile and wait for admin approval."
        } catch {
            onboardingMessage = error.localizedDescription
        }
    }
}
