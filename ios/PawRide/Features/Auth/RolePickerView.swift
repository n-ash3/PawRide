import SwiftUI

struct RolePickerView: View {
    @EnvironmentObject private var authStore: AuthStore

    var body: some View {
        VStack(spacing: 16) {
            Text("Choose Your Mode")
                .font(.title2.bold())
            Text("You can switch later in Settings.")
                .foregroundStyle(.secondary)

            if let user = authStore.user {
                ForEach(user.roles) { role in
                    Button {
                        Task { await authStore.switchRole(role) }
                    } label: {
                        HStack {
                            Text(role.displayName)
                                .font(.headline)
                            Spacer()
                            if user.activeRole == role {
                                Image(systemName: "checkmark.circle.fill")
                            }
                        }
                        .padding()
                        .background(PawRideTheme.card, in: RoundedRectangle(cornerRadius: 14))
                    }
                    .buttonStyle(.plain)
                }
            }
        }
        .padding()
        .background(PawRideTheme.background.ignoresSafeArea())
    }
}
