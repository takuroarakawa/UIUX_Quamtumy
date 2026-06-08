FROM rust:1.85-bookworm AS builder

RUN apt-get update \
  && apt-get install -y --no-install-recommends \
     pkg-config \
     libssl-dev \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY src ./src
COPY migrations ./migrations

RUN cargo build --release

FROM debian:bookworm-slim

RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY --from=builder /app/target/release/quantumy-auth-api /app/quantumy-auth-api
COPY --from=builder /app/migrations /app/migrations

ENV RUST_LOG=info
EXPOSE 3000

CMD ["/app/quantumy-auth-api"]

