import Foundation

/// Lightweight async HTTP client for academic API requests.
actor APIClient {
    static let shared = APIClient()

    private let session: URLSession
    private let decoder = JSONDecoder()

    private init() {
        let config = URLSessionConfiguration.default
        config.timeoutIntervalForRequest = 30
        config.timeoutIntervalForResource = 60
        config.httpAdditionalHeaders = [
            "Accept": "application/json",
            "User-Agent": "AcademicResearch-iOS/1.0"
        ]
        self.session = URLSession(configuration: config)
    }

    /// Perform a GET request and decode the JSON response.
    func get<T: Decodable>(
        url: String,
        params: [String: String] = [:],
        headers: [String: String] = [:]
    ) async throws -> T {
        guard var components = URLComponents(string: url) else {
            throw APIError.invalidURL(url)
        }

        if !params.isEmpty {
            components.queryItems = params.map { URLQueryItem(name: $0.key, value: $0.value) }
        }

        guard let requestURL = components.url else {
            throw APIError.invalidURL(url)
        }

        var request = URLRequest(url: requestURL)
        request.httpMethod = "GET"
        for (key, value) in headers {
            request.setValue(value, forHTTPHeaderField: key)
        }

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.networkError("Invalid response type")
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.httpError(statusCode: httpResponse.statusCode,
                                     body: String(data: data, encoding: .utf8) ?? "")
        }

        return try decoder.decode(T.self, from: data)
    }

    /// Perform a GET request and return raw JSON (for APIs with variable shapes).
    func getRaw(
        url: String,
        params: [String: String] = [:],
        headers: [String: String] = [:]
    ) async throws -> [String: Any] {
        guard var components = URLComponents(string: url) else {
            throw APIError.invalidURL(url)
        }
        if !params.isEmpty {
            components.queryItems = params.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        guard let requestURL = components.url else {
            throw APIError.invalidURL(url)
        }

        var request = URLRequest(url: requestURL)
        request.httpMethod = "GET"
        for (key, value) in headers {
            request.setValue(value, forHTTPHeaderField: key)
        }

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.networkError("Invalid response type")
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw APIError.httpError(statusCode: httpResponse.statusCode,
                                     body: String(data: data, encoding: .utf8) ?? "")
        }

        guard let json = try JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw APIError.decodingError("Response is not a JSON object")
        }
        return json
    }
}

enum APIError: LocalizedError {
    case invalidURL(String)
    case networkError(String)
    case httpError(statusCode: Int, body: String)
    case decodingError(String)
    case rateLimited

    var errorDescription: String? {
        switch self {
        case .invalidURL(let url):
            return "Invalid URL: \(url)"
        case .networkError(let msg):
            return "Network error: \(msg)"
        case .httpError(let code, _):
            if code == 429 { return "Rate limited — please wait a moment and try again." }
            return "Server error (HTTP \(code))"
        case .decodingError(let msg):
            return "Failed to parse response: \(msg)"
        case .rateLimited:
            return "Rate limited — please wait a moment and try again."
        }
    }
}
