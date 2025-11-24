// ========================================
// COGNITO SETUP
// ========================================

import { CognitoUserPool, CognitoUser, AuthenticationDetails } from 'amazon-cognito-identity-js';
import { COGNITO_USER_POOL_ID, COGNITO_CLIENT_ID } from './config';

const poolData = {
  UserPoolId: COGNITO_USER_POOL_ID,
  ClientId: COGNITO_CLIENT_ID,
};

export const userPool = new CognitoUserPool(poolData);

export { CognitoUser, AuthenticationDetails };

