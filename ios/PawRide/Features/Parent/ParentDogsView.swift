import SwiftUI

struct ParentDogsView: View {
    @EnvironmentObject private var authStore: AuthStore
    @State private var dogs: [DogProfile] = []
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            List {
                ForEach(dogs) { dog in
                    VStack(alignment: .leading, spacing: 4) {
                        Text(dog.name).font(.headline)
                        Text("\(dog.breed ?? "Unknown breed") • \(dog.size.capitalized)")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 6)
                }
                if let errorMessage {
                    Text(errorMessage).foregroundStyle(.red)
                }
            }
            .scrollContentBackground(.hidden)
            .background(PawRideTheme.background)
            .navigationTitle("My Dogs")
            .toolbar {
                Button("Add Dog") {}
            }
            .task {
                await loadDogs()
            }
            .refreshable {
                await loadDogs()
            }
        }
    }

    private func loadDogs() async {
        guard let token = authStore.accessToken else { return }
        do {
            dogs = try await APIClient.shared.fetchDogs(accessToken: token)
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}
